"""
db_models.py — SQLModel ORM table definitions.

WHAT IS AN ORM?
  ORM = Object-Relational Mapper. It lets you define database tables as Python
  classes and interact with them using Python objects instead of raw SQL strings.

  Without ORM:
    cursor.execute("INSERT INTO documents (id, filename) VALUES (?, ?)", (id, name))
    
  With SQLModel ORM:
    db.add(Document(id=id, filename=name))
    db.commit()

  The ORM generates the SQL for you, validates types, and gives you IDE autocomplete.

WHY SQLMODEL SPECIFICALLY?
  SQLModel is built on top of two libraries:
    - SQLAlchemy: the most mature Python ORM, used in almost every serious Python backend
    - Pydantic: FastAPI's validation library (which you already know from schemas.py)

  SQLModel merges them: one class is both the database table AND a Pydantic model.
  This eliminates the classic pain point of maintaining parallel "DB model" and
  "API schema" classes that have to be kept in sync manually.

WHAT DOES `table=True` MEAN?
  SQLModel has two modes:
    - SQLModel(table=True):  this class = a database table
    - SQLModel(table=False): this class = just a Pydantic model (no table)
  
  We use table=True here because Document IS a real database table.
  In schemas.py, our response models are table=False (just for API serialization).

PRIMARY KEY:
  Every database table needs a primary key — a column whose value uniquely
  identifies each row. We use a UUID string (e.g. "3f8a2b1c-...").
  
  Why UUID over auto-increment integer?
  - Auto-increment integers (1, 2, 3...) are sequential — they leak information
    (e.g. a user can guess there are only 5 documents by seeing document ID 5).
  - UUIDs are random → no information leakage.
  - UUIDs work across distributed systems (no central counter needed).
  - We already generate the UUID in rag_pipeline.py before inserting.

OPTIONAL FIELDS:
  Fields with `default=None` are optional. In a "nullable" column, the value
  can be NULL in SQL. We make `title` and `author` optional because many PDFs
  don't have these metadata fields set.

Interview angle:
  "What is the N+1 query problem?"
  Answer: When you load N records and then make N additional queries to load
  related data. Example: load 10 documents, then query each one's chunk count
  separately = 11 queries. Fix: use a JOIN or eager loading. We avoid this by
  storing chunk_count directly on the Document (denormalization — a conscious tradeoff).

  "When would you use SQLite vs. PostgreSQL?"
  Answer: SQLite is embedded (no server), single-writer, file-based — perfect for
  local dev, small-scale apps, or read-heavy workloads. PostgreSQL handles concurrent
  writes, large datasets, and complex queries. Migration between them with SQLAlchemy
  is just a connection string change (mostly).
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """
    Registered user account (V5 multi-tenancy).

    Each user owns their documents and repositories. Resource rows carry the
    owner's user_id so that every query/list/delete is scoped to the caller.
    Passwords are NEVER stored in plaintext — only a PBKDF2-HMAC-SHA256 hash
    via security.hash_password().
    """
    user_id: str = Field(primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    name: Optional[str] = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class Document(SQLModel, table=True):
    """
    Represents a single uploaded document in the system.
    
    This class does double duty:
      1. It IS the `document` table in SQLite (table=True).
      2. It IS a Pydantic model — you can validate data with it.

    Columns:
      document_id:     UUID string, primary key
      filename:        original filename from the upload
      file_hash:       SHA-256 hex digest of the file bytes
                       Used for duplicate detection. Has a unique constraint.
      file_size_bytes: raw file size for display in the UI
      page_count:      number of pages extracted from the PDF
      chunk_count:     number of chunks stored in ChromaDB
      title:           PDF metadata title (often empty)
      author:          PDF metadata author (often empty)
      uploaded_at:     UTC timestamp of ingestion
    """

    # Field(primary_key=True): this column is the table's primary key.
    # There's no auto-increment here — we generate UUIDs in the application layer.
    document_id: str = Field(primary_key=True)

    # Owner user_id (V5 multi-tenancy) — every resource is scoped to a user.
    owner_id: str = Field(index=True)

    # The original filename. Not unique — two different files can have the same name.
    filename: str

    # SHA-256 hash of the file content. Indexed (fast lookups) but NOT globally
    # unique in V5, because two different users may legitimately upload the same
    # file — dedup is scoped per owner in the application layer.
    file_hash: str = Field(index=True)

    # index=True on file_hash: creates a B-tree index on this column.
    # Without an index, "SELECT * WHERE file_hash = ?" scans every row (O(n)).
    # With an index, it's O(log n). Critical for duplicate detection on every upload.

    file_size_bytes: int

    page_count: int
    chunk_count: int

    # Optional PDF metadata fields — many PDFs don't populate these
    title: Optional[str] = Field(default=None)
    author: Optional[str] = Field(default=None)

    # default_factory: a callable that produces the default value.
    # We use lambda to call datetime.now(timezone.utc) at row creation time,
    # NOT at class definition time. This is an important Python distinction:
    #   default=datetime.now()           ← evaluated ONCE when class is defined (wrong!)
    #   default_factory=lambda: datetime.now() ← evaluated each time a row is created (correct!)
    uploaded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class Repository(SQLModel, table=True):
    """
    Represents an ingested code repository (from Git URL or ZIP upload).

    Columns:
      repo_id:          UUID primary key
      name:             repository name (e.g., 'fastapi' or uploaded folder name)
      clone_url:        source Git URL if cloned, or 'upload://<filename>' if uploaded via zip
      commit_hash:      latest commit SHA (if git repo)
      file_count:       number of source code files indexed
      chunk_count:      total number of syntax-aware chunks stored in ChromaDB
      primary_language: dominant programming language detected (e.g. 'Python', 'TypeScript')
      created_at:       timestamp of indexing
    """
    repo_id: str = Field(primary_key=True)
    owner_id: str = Field(index=True)
    name: str = Field(index=True)
    clone_url: Optional[str] = Field(default=None)
    commit_hash: Optional[str] = Field(default=None)
    file_count: int = Field(default=0)
    chunk_count: int = Field(default=0)
    primary_language: Optional[str] = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
