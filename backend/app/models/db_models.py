from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    user_id: str = Field(primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    name: Optional[str] = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class Document(SQLModel, table=True):
    document_id: str = Field(primary_key=True)
    owner_id: str = Field(index=True)
    filename: str
    file_hash: str = Field(index=True)
    file_size_bytes: int
    page_count: int
    chunk_count: int
    title: Optional[str] = Field(default=None)
    author: Optional[str] = Field(default=None)
    uploaded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class Repository(SQLModel, table=True):
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
