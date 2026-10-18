import logging
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from sqlmodel import Session, text
from app.services.document_registry import engine

print("BOOT: importing app.main ...", flush=True)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.api.routes import documents, query, code, evaluation, auth
from app.services.document_registry import create_db_and_tables

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("contexthub")


def _init_db_background() -> None:
    attempts = 20
    for attempt in range(1, attempts + 1):
        try:
            create_db_and_tables()
            logger.info("Database tables created/verified.")
            return
        except Exception as e:
            logger.warning(
                "DB schema init attempt %d/%d failed: %s", attempt, attempts, e
            )
            time.sleep(6)
    logger.error("Database schema init failed after %d attempts.", attempts)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 50)
    logger.info("ContextHub API starting up...")
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.repo_dir).mkdir(parents=True, exist_ok=True)
    logger.info("Upload dir:   %s", settings.upload_dir)
    logger.info("Repo dir:     %s", settings.repo_dir)
    logger.info("ChromaDB dir: %s", settings.chroma_persist_dir)
    logger.info("Database:     %s", settings.database_url)
    threading.Thread(target=_init_db_background, daemon=True).start()
    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to your .env file. "
            "Get a free key at: https://console.groq.com"
        )

    logger.info("LLM: Groq / %s", settings.groq_model)
    logger.info("Embeddings: %s", settings.embedding_model)
    logger.info("Auth: JWT HS256 (%d min expiry)", settings.jwt_expires_minutes)
    logger.info("=" * 50)
    yield
    logger.info("ContextHub API shutting down.")


app = FastAPI(
    title="ContextHub API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip().rstrip("/") for o in settings.cors_origins.split(",") if o.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(query.router)
app.include_router(code.router)
app.include_router(evaluation.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected internal error occurred. Please try again later."},
    )


@app.get("/health", tags=["System"])
async def health_check():
    error = None
    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1")).first()
    except Exception as e:
        error = str(e)
        logger.error("Health check: database unreachable: %s", e)

    return {
        "status": "ok" if error is None else "degraded",
        "service": "ContextHub API",
        "version": "1.0.0",
        "checks": {"database": "ok" if error is None else f"error: {error}"},
    }


@app.get("/", tags=["System"])
async def root():
    return {
        "message": "Welcome to ContextHub API. Visit /docs for the interactive API documentation.",
        "docs": "/docs",
    }
