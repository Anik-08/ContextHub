"""
config.py — Centralised application settings using pydantic-settings.

Why pydantic-settings?
  - Reads values from environment variables or a .env file automatically.
  - Validates types at startup (e.g. raises an error if GROQ_API_KEY is missing).
  - One source of truth: all tuneable parameters live here, not scattered in code.

Interview angle:
  "How do you manage configuration and secrets in a Python service?"
  Answer: Environment variables loaded via pydantic-settings. Never hardcode secrets.
  In production you'd use a secrets manager (AWS Secrets Manager, HashiCorp Vault).
"""

from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import secrets


def _random_secret() -> str:
    """Generate a random 64-hex-char secret for JWT signing (dev default)."""
    return secrets.token_hex(32)


class Settings(BaseSettings):
    # -----------------------------------------------------------------
    # Security (V5)
    # -----------------------------------------------------------------
    # SECRET_KEY signs JWT access tokens. In production, ALWAYS set this in
    # your environment / secret manager. The random default means tokens are
    # invalidated every time the server restarts — fine for dev, never for prod.
    secret_key: str = Field(default_factory=_random_secret)

    # How long an access token stays valid before the client must re-login.
    jwt_expires_minutes: int = 60 * 24  # 24 hours

    # -----------------------------------------------------------------
    # Database (V5)
    # -----------------------------------------------------------------
    # If DATABASE_URL is set (e.g. postgresql://user:pass@host/db) it wins.
    # Otherwise we fall back to local SQLite for zero-setup development.
    database_url: str = "sqlite:///./contexthub.db"

    # -----------------------------------------------------------------
    # CORS
    # -----------------------------------------------------------------
    # Comma-separated list of allowed browser origins (the frontend).
    # In production set this to your Vercel/Next.js frontend URL, e.g.:
    #   CORS_ORIGINS=https://contexthub.vercel.app,https://contexthub-xyz.vercel.app
    cors_origins: str = (
        "http://localhost:3000,http://localhost:3001,"
        "http://127.0.0.1:3000,http://127.0.0.1:3001"
    )

    # -----------------------------------------------------------------
    # LLM — Groq
    # -----------------------------------------------------------------
    # Groq gives us fast inference on open-source models (Llama 3, Mixtral).
    # Speed matters for RAG because we're making multiple LLM calls per session.
    groq_api_key: str

    # The model we send to Groq.
    # groq/compound-mini — fast, generous free-tier quota, no reasoning overhead.
    # Alternatives: openai/gpt-oss-20b (reasoning; Groq SDK returns answer cleanly),
    #               qwen/qwen3.8-27b (requires reasoning_effort="none").
    groq_model: str = "groq/compound-mini"

    # Max output tokens for LLM calls. Kept well under free-tier OTPM limits
    # (typically 1000 tokens/min). Set lower to avoid 429 on reasoning models.
    llm_max_tokens: int = 600

    # -----------------------------------------------------------------
    # Embeddings
    # -----------------------------------------------------------------
    # We use sentence-transformers locally — no API key, no cost, runs on CPU.
    # all-MiniLM-L6-v2: 384-dimensional embeddings, 80MB model, fast.
    # Trade-off: lower quality than OpenAI ada-002 (1536-dim), but free.
    embedding_model: str = "all-MiniLM-L6-v2"

    # -----------------------------------------------------------------
    # Chunking parameters
    # -----------------------------------------------------------------
    # chunk_size: max characters per chunk.
    # Too large → chunk carries too much irrelevant text, dilutes the answer.
    # Too small → chunk loses surrounding context, answer misses meaning.
    # 1000 chars ≈ ~150-200 words. Good default for prose documents.
    chunk_size: int = 1000

    # chunk_overlap: how many characters the next chunk shares with the previous.
    # Why overlap? So that sentences/ideas that span a chunk boundary are
    # captured in at least one chunk. Without overlap, you'd lose context
    # at every boundary.
    chunk_overlap: int = 200

    # -----------------------------------------------------------------
    # Retrieval parameters
    # -----------------------------------------------------------------
    # How many chunks to retrieve from ChromaDB per query.
    # More chunks → more context for the LLM, but also more noise + cost.
    # 5 is a solid default. V4 will tune this with reranking.
    top_k_results: int = 5

    # -----------------------------------------------------------------
    # Storage paths
    # -----------------------------------------------------------------
    chroma_persist_dir: str = "./chroma_data"
    upload_dir: str = "./uploads"
    repo_dir: str = "./repos"

    # -----------------------------------------------------------------
    # Vector DB — ChromaDB connection mode
    # -----------------------------------------------------------------
    # Local mode (default): PersistentClient writes to chroma_persist_dir on
    # local disk. Perfect for docker-compose / dev.
    #
    # Remote mode: set CHROMA_HOST to point at a hosted Chroma instance
    # (e.g. Chroma Cloud or a self-hosted chroma server). Required on hosts
    # with ephemeral disks (Render free tier) where local data is wiped.
    #   CHROMA_HOST=xxxxx.chroma.app (or ...trychroma.com)
    #   CHROMA_PORT=8000  (always 8000 with ssl=true for Chroma Cloud)
    #   CHROMA_SSL=true
    #   CHROMA_API_KEY=<token>            (Chroma Cloud uses X-Chroma-Token)
    #   CHROMA_TENANT=default-tenant      (optional; Chroma Cloud may assign one)
    #   CHROMA_DATABASE=default_database  (optional)
    chroma_host: Optional[str] = None
    chroma_port: int = 8000
    chroma_ssl: bool = False
    chroma_api_key: Optional[str] = None
    chroma_tenant: Optional[str] = None
    chroma_database: Optional[str] = None

    # Backward-compatible alias: pydantic-settings default for the DB path.
    db_path: str = "sqlite:///./contexthub.db"

    # -----------------------------------------------------------------
    # Code RAG parameters (V3)
    # -----------------------------------------------------------------
    code_chunk_size: int = 1500
    code_chunk_overlap: int = 200

    # -----------------------------------------------------------------
    # pydantic-settings magic: read from .env file
    # -----------------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # don't crash on unknown env vars
    )

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        """
        Coerce bare Postgres URLs to use the psycopg (v3) SQLAlchemy dialect,
        which is the driver we install. SQLAlchemy otherwise assumes psycopg2
        (not installed) for a plain `postgresql://` URL.
        """
        if v.startswith("postgres://") or v.startswith("postgresql://"):
            if not any(prefix in v for prefix in ("+psycopg", "+psycopg2", "+pg8000")):
                return v.replace(
                    "postgresql://", "postgresql+psycopg://", 1
                ).replace("postgres://", "postgresql+psycopg://", 1)
        return v


# Singleton: import this object everywhere instead of instantiating Settings() repeatedly.
# This is the standard Python pattern for app-wide config.
settings = Settings()
