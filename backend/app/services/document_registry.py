"""
document_registry.py — SQLite CRUD operations for the document registry.

THE REPOSITORY PATTERN:
  This module is a "repository" — it owns all database access for documents.
  Routes and other services call functions here; they never write SQL directly.
  
  Benefits:
    - If you swap SQLite for PostgreSQL, only this file changes.
    - Database logic is testable in isolation (mock the DB session in tests).
    - Consistent error handling in one place.
  
  This is one of the most common software design patterns asked about in
  backend engineering interviews.

HOW SQLMODEL / SQLALCHEMY SESSIONS WORK:
  A "session" is a unit of work with the database.
  
  Think of it like a shopping basket at checkout:
    - You ADD items to the basket (session.add(record))
    - Nothing goes to the database yet — it's all in memory
    - When you COMMIT (session.commit()), everything in the basket is written atomically
    - If something fails before commit, nothing is written (atomicity)
    - session.refresh(record) re-reads the row from DB to get server-generated values
  
  This is a database TRANSACTION. ACID properties:
    - Atomicity:   all-or-nothing commit
    - Consistency: constraints enforced (e.g. unique hash)
    - Isolation:   concurrent sessions don't interfere
    - Durability:  committed data survives crashes

ENGINE vs SESSION:
  - Engine: the connection pool to the database. Created once, reused.
  - Session: a single conversation with the DB. Created per operation, then closed.
  
  Using a context manager (with Session(engine) as session:) ensures the session
  is always closed, even if an exception occurs. Critical for preventing
  "connection leak" bugs that exhaust the connection pool under load.

CONNECT_ARGS {"check_same_thread": False}:
  SQLite's default is single-threaded. FastAPI is async and multi-threaded.
  This flag tells SQLite to allow access from multiple threads.
  For PostgreSQL, this is not needed — it handles concurrency natively.

Interview angle:
  "What is the difference between optimistic and pessimistic locking?"
  Answer: Pessimistic locking locks the row when you read it (prevents others writing).
  Optimistic locking: no lock on read; at write time, check if the row changed
  (using a version column). If it did, abort and retry.
  SQLite uses pessimistic locking at the file level. PostgreSQL supports both.
  Our use case (document ingestion) doesn't need row-level locking in V2.

  "What is connection pooling?"
  Answer: Opening a new DB connection is expensive (~5-10ms). A connection pool
  keeps a set of open connections and reuses them across requests.
  SQLAlchemy manages this automatically. In production with PostgreSQL, you'd
  tune pool_size and max_overflow based on your traffic.
"""

import hashlib
from pathlib import Path

from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select

from app.config import settings
from app.models.db_models import Document, Repository, User


# ---------------------------------------------------------------------------
# Engine — one per process, shared across all requests
# ---------------------------------------------------------------------------
# V5: SUPPORTS BOTH SQLite AND POSTGRESQL
#   - If DATABASE_URL looks like postgresql://... we connect to Postgres.
#   - Otherwise we fall back to a local SQLite file (zero-setup dev).
#
# Differences handled here:
#   - SQLite needs connect_args={"check_same_thread": False} because it's a
#     single-file DB that FastAPI touches from multiple threads.
#   - Postgres handles concurrency natively and can't use that argument.
database_url = settings.database_url
connect_args: dict = {}
if database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    database_url,
    connect_args=connect_args,
    pool_pre_ping=True,  # verify stale Postgres connections before reuse
    # echo=True would print every SQL statement to stdout — useful for debugging
    # but noisy in production. Set to True temporarily if you want to see the SQL.
    echo=False,
)


# ---------------------------------------------------------------------------
# Table creation — called once at app startup
# ---------------------------------------------------------------------------

def create_db_and_tables() -> None:
    """
    Create all database tables defined by SQLModel classes with table=True.
    
    SQLModel.metadata.create_all() generates and runs CREATE TABLE IF NOT EXISTS
    statements for every SQLModel table class it knows about.
    
    IMPORTANT: This only works for classes that have been IMPORTED before this
    call. Python only knows about a class if its module has been imported.
    db_models.py is imported at the top of this file, so Document is registered.
    
    Idempotent: safe to call on every startup — IF NOT EXISTS means it won't
    drop existing data or recreate tables that already exist.
    
    In production (V5): we'd use Alembic for migrations instead of create_all().
    Alembic tracks schema changes and generates migration scripts, so you can
    ALTER TABLE safely without losing data. create_all() can't alter existing tables.
    """
    SQLModel.metadata.create_all(engine)
    print("Database tables created/verified.")


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def create_document(
    document_id: str,
    filename: str,
    file_hash: str,
    file_size_bytes: int,
    page_count: int,
    chunk_count: int,
    owner_id: str,
    title: str = "",
    author: str = "",
) -> Document:
    """
    Insert a new document record into the database.

    owner_id: the user who uploaded/owns the document (V5 multi-tenancy).
    
    Called after successful PDF ingestion in rag_pipeline.py.
    
    Returns the newly created Document ORM object (with uploaded_at populated).
    
    Why return the object? So the caller (rag_pipeline.py) can access
    the generated uploaded_at timestamp for the API response.
    """
    doc = Document(
        document_id=document_id,
        owner_id=owner_id,
        filename=filename,
        file_hash=file_hash,
        file_size_bytes=file_size_bytes,
        page_count=page_count,
        chunk_count=chunk_count,
        title=title or None,
        author=author or None,
    )

    # Context manager: session is automatically closed when the `with` block exits,
    # even if an exception is raised. This prevents connection leaks.
    with Session(engine) as session:
        session.add(doc)    # stage the INSERT
        session.commit()    # execute the INSERT atomically
        session.refresh(doc)  # reload from DB to get server-computed values (uploaded_at)

    return doc


def get_all_documents(owner_id: str) -> list[Document]:
    """
    Retrieve all documents for one user, ordered by upload time (newest first).
    
    Multi-tenancy: every list is filtered by owner_id — users never see each
    other's documents.
    
    Equivalent raw SQL:
        SELECT * FROM document WHERE owner_id = ? ORDER BY uploaded_at DESC;
    """
    with Session(engine) as session:
        statement = (
            select(Document)
            .where(Document.owner_id == owner_id)
            .order_by(Document.uploaded_at.desc())
        )
        results = session.exec(statement).all()
    return list(results)


def get_document_by_id(document_id: str, owner_id: str) -> Document | None:
    """
    Fetch a document by primary key, scoped to the owning user.
    
    Returns None if not found OR if it belongs to a different user —
    the caller decides whether to raise 404. Scoping by owner_id here is the
    multi-tenant access control: a user can only read/delete/query their own
    documents (querying by a UUID that isn't yours is a "not found").
    """
    with Session(engine) as session:
        statement = select(Document).where(
            Document.document_id == document_id,
            Document.owner_id == owner_id,
        )
        return session.exec(statement).first()


def get_document_by_hash(file_hash: str, owner_id: str) -> Document | None:
    """
    Look up a document owned by this user by its SHA-256 file hash.
    
    Used for per-owner duplicate detection: before ingesting a PDF, we hash it
    and call this function. If it returns a Document, we skip re-ingestion
    (another user uploading the same file still gets their own copy).
    """
    with Session(engine) as session:
        statement = select(Document).where(
            Document.file_hash == file_hash,
            Document.owner_id == owner_id,
        )
        return session.exec(statement).first()


def delete_document(document_id: str, owner_id: str) -> bool:
    """
    Delete a document record from the database (scoped to the owner).
    
    Returns True if a record was deleted, False if the document wasn't found
    (including "found but owned by someone else" — we treat that as not found
    so we don't leak existence).
    """
    with Session(engine) as session:
        statement = select(Document).where(
            Document.document_id == document_id,
            Document.owner_id == owner_id,
        )
        doc = session.exec(statement).first()
        if not doc:
            return False
        session.delete(doc)
        session.commit()
    return True


# ---------------------------------------------------------------------------
# Repository CRUD (V3)
# ---------------------------------------------------------------------------

def create_repository(
    repo_id: str,
    name: str,
    clone_url: str | None,
    commit_hash: str | None,
    file_count: int,
    chunk_count: int,
    primary_language: str | None,
    owner_id: str,
) -> Repository:
    """
    Save an indexed codebase repository record, owned by `owner_id`.
    """
    repo = Repository(
        repo_id=repo_id,
        owner_id=owner_id,
        name=name,
        clone_url=clone_url,
        commit_hash=commit_hash,
        file_count=file_count,
        chunk_count=chunk_count,
        primary_language=primary_language,
    )
    with Session(engine) as session:
        session.add(repo)
        session.commit()
        session.refresh(repo)
    return repo


def get_all_repositories(owner_id: str) -> list[Repository]:
    """
    List all repositories owned by a user, newest first.
    """
    with Session(engine) as session:
        statement = (
            select(Repository)
            .where(Repository.owner_id == owner_id)
            .order_by(Repository.created_at.desc())
        )
        return list(session.exec(statement).all())


def get_repository_by_id(repo_id: str, owner_id: str) -> Repository | None:
    """
    Fetch a single repository record, scoped to the owning user.
    """
    with Session(engine) as session:
        statement = select(Repository).where(
            Repository.repo_id == repo_id,
            Repository.owner_id == owner_id,
        )
        return session.exec(statement).first()


def delete_repository(repo_id: str, owner_id: str) -> bool:
    """
    Delete a repository metadata record (scoped to the owner).
    """
    with Session(engine) as session:
        statement = select(Repository).where(
            Repository.repo_id == repo_id,
            Repository.owner_id == owner_id,
        )
        repo = session.exec(statement).first()
        if not repo:
            return False
        session.delete(repo)
        session.commit()
    return True



# ---------------------------------------------------------------------------
# Utility: hash a file
# ---------------------------------------------------------------------------

def hash_file(file_path: str | Path) -> str:
    """
    Compute the SHA-256 hash of a file's contents.
    
    WHY SHA-256?
      SHA-256 is a cryptographic hash function:
        - Deterministic: same file → always same hash
        - Collision-resistant: astronomically unlikely for two different files
          to produce the same hash (2^256 possible hashes)
        - One-way: you can't reverse the hash to get the original file
      
      We use it here for identity, not security — we just want a unique
      fingerprint for the file content.
    
    WHY READ IN CHUNKS?
      file.read() loads the entire file into memory.
      For a 500MB PDF, that's 500MB of RAM consumed for one hash operation.
      Reading in 8KB chunks keeps memory usage constant regardless of file size.
      This is called "streaming" — process data in fixed-size pieces.
    
    Args:
        file_path: path to the file to hash
    
    Returns:
        hex string of the SHA-256 digest, e.g. "a3f9b2c1d4e5..."
    """
    sha256 = hashlib.sha256()
    chunk_size = 8192  # 8KB chunks

    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            # The walrus operator (:=) assigns AND tests in one expression:
            # while chunk := f.read(8192) → read 8KB, assign to `chunk`, loop if non-empty
            sha256.update(chunk)

    return sha256.hexdigest()  # returns lowercase hex string
