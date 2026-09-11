# ContextHub Backend — production image
# Multi-stage: build deps in a heavy stage, runtime in a slim stage.

# Stage 1: build dependencies
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps needed for pymupdf + sentence-transformers wheels at build time
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
# Install the project deps into a venv inside the image (fast, reproducible)
RUN pip install --upgrade pip && \
    pip install uv && \
    uv sync --frozen --no-dev --no-install-project

# Stage 2: runtime
FROM python:3.13-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy the pre-built venv from the builder stage
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application source
COPY app ./app

# Create data directories (mount volumes here in compose)
RUN mkdir -p /app/chroma_data /app/uploads /app/repos

EXPOSE 8000

# Healthcheck: the API exposes /health for orchestration probes
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]