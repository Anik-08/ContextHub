from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
import secrets


def _random_secret() -> str:
    return secrets.token_hex(32)


def _file_storage_dir(name: str) -> str:
    if os.getenv("VERCEL") == "1":
        return f"/tmp/{name}"
    return f"./{name}"


class Settings(BaseSettings):
    secret_key: str = Field(default_factory=_random_secret)
    jwt_expires_minutes: int = 60 * 24
    database_url: str = "sqlite:///./contexthub.db"
    cors_origins: str = (
        "http://localhost:3000,http://localhost:3001,"
        "http://127.0.0.1:3000,http://127.0.0.1:3001"
    )
    groq_api_key: str
    groq_model: str = "groq/compound-mini"
    llm_max_tokens: int = 600
    embedding_model: str = "all-MiniLM-L6-v2"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k_results: int = 5
    chroma_persist_dir: str = Field(default_factory=lambda: _file_storage_dir("chroma_data"))
    upload_dir: str = Field(default_factory=lambda: _file_storage_dir("uploads"))
    repo_dir: str = Field(default_factory=lambda: _file_storage_dir("repos"))
    chroma_host: Optional[str] = None
    chroma_port: int = 8000
    chroma_ssl: bool = False
    chroma_api_key: Optional[str] = None
    chroma_tenant: Optional[str] = None
    chroma_database: Optional[str] = None
    code_chunk_size: int = 1500
    code_chunk_overlap: int = 200
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        if v.startswith("postgres://") or v.startswith("postgresql://"):
            if not any(prefix in v for prefix in ("+psycopg", "+psycopg2", "+pg8000")):
                return v.replace(
                    "postgresql://", "postgresql+psycopg://", 1
                ).replace("postgres://", "postgresql+psycopg://", 1)
        return v


settings = Settings()
