import hashlib
from pathlib import Path

from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select

from app.config import settings
from app.models.db_models import Document, Repository


database_url = settings.database_url
connect_args: dict = {}
if database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    print("Database tables created/verified.")


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
    with Session(engine) as session:
        session.add(doc)
        session.commit()
        session.refresh(doc)

    return doc


def get_all_documents(owner_id: str) -> list[Document]:
    with Session(engine) as session:
        statement = (
            select(Document)
            .where(Document.owner_id == owner_id)
            .order_by(Document.uploaded_at.desc())
        )
        results = session.exec(statement).all()
    return list(results)


def get_document_by_id(document_id: str, owner_id: str) -> Document | None:
    with Session(engine) as session:
        statement = select(Document).where(
            Document.document_id == document_id,
            Document.owner_id == owner_id,
        )
        return session.exec(statement).first()


def get_document_by_hash(file_hash: str, owner_id: str) -> Document | None:
    with Session(engine) as session:
        statement = select(Document).where(
            Document.file_hash == file_hash,
            Document.owner_id == owner_id,
        )
        return session.exec(statement).first()


def delete_document(document_id: str, owner_id: str) -> bool:
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
    with Session(engine) as session:
        statement = (
            select(Repository)
            .where(Repository.owner_id == owner_id)
            .order_by(Repository.created_at.desc())
        )
        return list(session.exec(statement).all())


def get_repository_by_id(repo_id: str, owner_id: str) -> Repository | None:
    with Session(engine) as session:
        statement = select(Repository).where(
            Repository.repo_id == repo_id,
            Repository.owner_id == owner_id,
        )
        return session.exec(statement).first()


def delete_repository(repo_id: str, owner_id: str) -> bool:
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


def hash_file(file_path: str | Path) -> str:
    sha256 = hashlib.sha256()
    chunk_size = 8192
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)

    return sha256.hexdigest()
