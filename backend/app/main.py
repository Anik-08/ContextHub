"""
main.py — FastAPI application factory and server entry point.

WHY "APP FACTORY" PATTERN?
  We create the FastAPI app here and include all routers.
  This is the central place that wires everything together.
  
  In larger apps, this becomes a factory function create_app() that
  accepts config — useful for creating different instances for testing vs. production.

CORS (Cross-Origin Resource Sharing):
  When the browser (at localhost:3000 — Next.js) makes a request to our API
  (at localhost:8000 — FastAPI), the browser's security policy blocks it by default.
  This is called the "Same-Origin Policy".
  
  CORS middleware tells the browser: "It's OK, these origins are allowed to talk to us."
  
  In development: we allow localhost:3000 (Next.js dev server).
  In production: we'd list the actual frontend domain (e.g., https://contexthub.com).
  NEVER use allow_origins=["*"] in production — it allows any website to call your API.

LIFESPAN (startup/shutdown events):
  FastAPI's lifespan context manager runs code at server startup and shutdown.
  We use it to create required directories and validate config at startup.
  If GROQ_API_KEY is missing, we fail fast with a clear error at startup —
  better than a cryptic error on the first request.

Interview angle:
  "How do you handle CORS in a FastAPI application?"
  Answer: Use CORSMiddleware, specifying allowed origins, methods, and headers.
  In dev, allow localhost ports. In production, restrict to exact frontend domains.
  Never use wildcard origins in production as it's a security vulnerability.
"""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.api.routes import documents, query, code, evaluation, auth
from app.services.document_registry import create_db_and_tables


# ---------------------------------------------------------------------------
# Logging (V5 production hardening)
# ---------------------------------------------------------------------------
# A single, structured logger for the whole app. In production you'd ship logs
# to a collector (DataDog, Grafana Loki, AWS CloudWatch) rather than stdout.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("contexthub")


# ---------------------------------------------------------------------------
# Lifespan: runs at startup and shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Code before 'yield' runs at server startup.
    Code after 'yield' runs at server shutdown.
    
    This replaces the old @app.on_event("startup") pattern (deprecated in newer FastAPI).
    """
    # Startup
    logger.info("=" * 50)
    logger.info("ContextHub API starting up...")
    
    # Ensure required directories exist
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.repo_dir).mkdir(parents=True, exist_ok=True)
    logger.info("Upload dir:   %s", settings.upload_dir)
    logger.info("Repo dir:     %s", settings.repo_dir)
    logger.info("ChromaDB dir: %s", settings.chroma_persist_dir)
    
    # Initialize database schema
    create_db_and_tables()
    logger.info("Database:     %s", settings.database_url)
    
    # Validate Groq API key is present
    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to your .env file. "
            "Get a free key at: https://console.groq.com"
        )
    
    logger.info("LLM: Groq / %s", settings.groq_model)
    logger.info("Embeddings: %s", settings.embedding_model)
    logger.info("Auth: JWT HS256 (%d min expiry)", settings.jwt_expires_minutes)
    logger.info("=" * 50)
    
    yield  # Server is now running — handle requests
    
    # Shutdown (cleanup if needed)
    logger.info("ContextHub API shutting down.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ContextHub API",
    description=(
        "Enterprise Knowledge & Code Intelligence Platform. "
        "Upload PDFs and ask questions. Powered by RAG + Groq."
    ),
    version="1.0.0",
    lifespan=lifespan,
    # docs_url: where the Swagger UI lives. Default is /docs.
    docs_url="/docs",
    # redoc_url: alternative API docs UI (ReDoc). /redoc
    redoc_url="/redoc",
)


# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    # In development: allow the Next.js dev server
    # In production: replace with your actual frontend domain
    allow_origins=[
        "http://localhost:3000",  # Next.js default port
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],   # GET, POST, PUT, DELETE, OPTIONS, etc.
    allow_headers=["*"],   # Authorization, Content-Type, etc.
)


# ---------------------------------------------------------------------------
# Include routers
# ---------------------------------------------------------------------------

# Each router adds its routes to the app with its configured prefix.
# auth.router          → /api/auth/*
# documents.router     → POST /api/documents/upload
# query.router         → POST /api/query
# code.router          → /api/code/*
# evaluation.router    → POST /api/evaluate
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(query.router)
app.include_router(code.router)
app.include_router(evaluation.router)


# ---------------------------------------------------------------------------
# Global exception handling (V5 hardening)
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catch-all handler: prevents stack traces leaking to clients, logs the full
    error server-side, and returns a clean 500 JSON body.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected internal error occurred. Please try again later."},
    )


# ---------------------------------------------------------------------------
# Health check endpoint (V5: verifies real dependencies, not just liveness)
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
async def health_check():
    """
    Readiness probe. In production, load balancers / orchestrators poll this.
    It checks the real dependencies (database reachability) rather than just
    returning 200 blindly, so we fail fast when a backing store is down.
    """
    db_ok = True
    db_error = None
    try:
        from sqlmodel import Session, text
        from app.services.document_registry import engine
        with Session(engine) as session:
            session.exec(text("SELECT 1")).first()
    except Exception as e:
        db_ok = False
        db_error = str(e)
        logger.error("Health check: database unreachable: %s", e)

    status_code = "ok" if db_ok else "degraded"
    return {
        "status": status_code,
        "service": "ContextHub API",
        "version": "1.0.0",
        "checks": {
            "database": "ok" if db_ok else f"error: {db_error}",
        },
    }


@app.get("/", tags=["System"])
async def root():
    """Root endpoint — redirects users to the docs."""
    return {
        "message": "Welcome to ContextHub API. Visit /docs for the interactive API documentation.",
        "docs": "/docs",
    }
