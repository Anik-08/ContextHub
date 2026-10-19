# ContextHub

**Grounded RAG for documents & code.** ContextHub turns PDFs and Git repositories into a queryable knowledge base. Every answer cites the exact PDF page or the exact file and line range it came from — no ungrounded guesses.

Upload a policy PDF, clone a repo, ask *"Where is user authentication handled?"*, and get an answer backed by retrievable sources with transparency scores.

## Features

- **PDF knowledge base** — Upload PDFs (deduplicated by SHA-256), chunked with a recursive character splitter, embedded, and indexed for semantic search.
- **Codebase intelligence** — Clone a public Git repo or upload a `.zip`. Files are chunked along language syntax boundaries so answers cite exact files and line ranges.
- **Hybrid retrieval** — Dense vector search (ChromaDB) fused with sparse BM25 keyword search via Reciprocal Rank Fusion (RRF), then refined with a two-stage cross-encoder reranker. Search modes: `hybrid`, `dense`, `sparse`.
- **Grounded generation** — Groq-hosted LLM generates answers with inline page/line citations. Out-of-domain or irrelevant questions are gracefully refused via relevance guardrails.
- **RAG Triad evaluation** — LLM-as-a-judge benchmarking scores Context Relevance, Faithfulness, and Answer Relevance (0.0–1.0) with reasoning for each dimension.
- **Multi-tenant auth** — JWT-secured API (HS256). PBKDF2-hashed passwords. Per-user document and repository ownership.
- **Large-file upload flow** — On serverless hosts, the browser streams files directly to Vercel Blob (bypassing the 4.5 MB function body limit); the backend pulls the blob and ingests it.

## Architecture

```mermaid
flowchart TB
    subgraph Client
        B[Browser]
    end

    subgraph Frontend["Frontend — Next.js 16 (port 3000)"]
        UI["App Router pages<br/>Landing · Auth · Dashboard<br/>Query · Repositories · Evaluate"]
        APIR["/api/upload route<br/>JWT-verified Blob token"]
        LIB["lib/auth.tsx · lib/api.ts<br/>JWT in localStorage"]
    end

    subgraph Backend["Backend — FastAPI (port 8000)"]
        AUTH["/api/auth<br/>register · login · me"]
        DOC["/api/documents<br/>upload · list · delete"]
        CODE["/api/code<br/>ingest-git · upload-zip · query"]
        QRY["/api/query"]
        EVAL["/api/evaluate"]
        HLTH["/health"]
    end

    subgraph Pipeline["RAG Pipeline"]
        PDF["PyMuPDF<br/>text extraction"]
        CHUNK["Recursive chunker<br/>prose + language-aware code"]
        EMB["Embedder<br/>all-MiniLM-L6-v2 (384-d)"]
        BM25["BM25 sparse index"]
        HYB["Hybrid retriever<br/>RRF fusion + cross-encoder rerank"]
        LLM["Groq LLM<br/>grounded answer + citations"]
        JUDGE["LLM-as-a-judge<br/>RAG Triad scoring"]
    end

    subgraph Data["Data Stores"]
        DB[("SQLModel<br/>SQLite / PostgreSQL<br/>users · documents · repos")]
        CH[("ChromaDB<br/>vector store<br/>doc + code collections")]
        BLOB[("Vercel Blob<br/>PDF / ZIP files")]
    end

    B --> UI
    UI --> LIB
    B -.client upload.-> APIR
    APIR -.upload token.-> BLOB
    BLOB -.blob URL.-> DOC
    BLOB -.blob URL.-> CODE

    UI -- "HTTP + Bearer JWT" --> AUTH
    UI --> DOC
    UI --> CODE
    UI --> QRY
    UI --> EVAL
    B -.liveness/readiness.-> HLTH

    AUTH --> DB
    DOC --> PDF --> CHUNK --> EMB --> CH
    DOC --> DB
    DOC -.download blob.-> BLOB
    CODE --> CHUNK
    CODE --> DB
    CODE --> CH
    CODE -.download blob.-> BLOB

    QRY --> HYB
    HYB --> CH
    HYB --> BM25
    HYB --> LLM
    LLM --> QRY

    EVAL --> JUDGE
    JUDGE --> HYB
    JUDGE --> LLM
```

### Retrieval flow (per query)

1. **Stage 1 — High recall**: dense vector search (ChromaDB) and sparse BM25 each return ~20 candidates; the lists are fused with Reciprocal Rank Fusion.
2. **Stage 2 — High precision**: a cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) re-scores the fused candidates down to the final top-k.
3. **Generation**: the reranked chunks are assembled into a context block; the Groq LLM answers with inline citations and a relevance guardrail.
4. **Evaluation** (optional): the same query is re-run through an LLM-as-a-judge that scores the RAG Triad.

## Tech stack

| Layer      | Technology |
|------------|------------|
| Frontend   | Next.js 16 (App Router), React 19, Tailwind CSS v4, TypeScript |
| Backend    | FastAPI, SQLModel, Pydantic-settings, Python 3.13 |
| Vector DB  | ChromaDB (local persistent client, or Chroma Cloud / self-hosted via `CHROMA_HOST`) |
| Relational DB | SQLite (zero-setup dev) or PostgreSQL (prod / Docker Compose) |
| Embeddings | `sentence-transformers` `all-MiniLM-L6-v2` (384-dim, local CPU) |
| Reranker   | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| LLM        | Groq (`groq/compound-mini` default; other Groq models supported) |
| Auth       | JWT (HS256, PyJWT) + PBKDF2-HMAC-SHA256 password hashing |
| File storage | Local disk (dev) or Vercel Blob (serverless / large uploads) |
| Deploy     | Docker Compose (local), Render (backend), Vercel (frontend + Blob) |

## Local setup

### Prerequisites

- **Python 3.13+** (with [uv](https://docs.astral.sh/uv/) recommended) or Docker
- **Node.js 20+** (with npm) or Docker
- A free **Groq API key** — [console.groq.com](https://console.groq.com)

### Option A — Docker Compose (recommended)

```bash
git clone <repo-url> 
cd ContextHub

# Create a root .env (read by docker-compose.yml)
cat > .env <<'EOF'
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=groq/compound-mini
DATABASE_URL=postgresql+psycopg://contexthub:contexthub@postgres:5432/contexthub
SECRET_KEY=change-me-to-a-long-random-string
EOF

docker compose up --build
```

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend API + Swagger: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health check: [http://localhost:8000/health](http://localhost:8000/health)

Compose provisions PostgreSQL 17, the FastAPI backend, and the Next.js frontend with persistent volumes for Postgres data, Chroma vectors, uploads, and cloned repos.

### Option B — Manual (no Docker)

**Backend**

```bash
cd backend
cp .env.example .env        # then edit: set GROQ_API_KEY (required)
uv sync                     # create venv + install deps (or: pip install -e .)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Without `uv`:

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

By default the backend uses local SQLite (`./contexthub.db`) and a local ChromaDB directory (`./chroma_data`) — zero external services needed. Set `DATABASE_URL` and/or `CHROMA_HOST` in `backend/.env` to use PostgreSQL or a hosted Chroma instance.

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Register an account, then upload a PDF or ingest a repo from the dashboard.

### Environment variables

Defined in `backend/.env` (see `backend/.env.example` for the full annotated list):

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `GROQ_API_KEY` | **yes** | — | Groq API key for LLM calls |
| `SECRET_KEY` | prod | random per-boot | JWT signing key |
| `DATABASE_URL` | no | `sqlite:///./contexthub.db` | Postgres or SQLite connection string |
| `CORS_ORIGINS` | no | localhost:3000/3001 | Comma-separated allowed browser origins |
| `GROQ_MODEL` | no | `groq/compound-mini` | Groq model id |
| `LLM_MAX_TOKENS` | no | `600` | Max output tokens per LLM call |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | no | `1000` / `200` | Prose chunking parameters |
| `CODE_CHUNK_SIZE` / `CODE_CHUNK_OVERLAP` | no | `1500` / `200` | Code chunking parameters |
| `TOP_K_RESULTS` | no | `5` | Chunks retrieved per query |
| `CHROMA_HOST` / `CHROMA_PORT` / `CHROMA_SSL` / `CHROMA_API_KEY` | no | local disk | Remote Chroma (Chroma Cloud or self-hosted) |
| `CHROMA_PERSIST_DIR` / `UPLOAD_DIR` / `REPO_DIR` | no | `./chroma_data`, `./uploads`, `./repos` | Local storage paths |
| `BLOB_READ_WRITE_TOKEN` | prod | — | Vercel Blob token (backend + frontend `/api/upload` route) |
| `NEXT_PUBLIC_API_URL` | yes (frontend) | `http://localhost:8000` | Backend base URL used by the frontend |

The frontend `/api/upload` route also verifies JWTs with `SECRET_KEY` — set the same value in both backend and frontend environments in production.

## API overview

All endpoints except `/health` require `Authorization: Bearer <token>`.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Create account → token + user |
| POST | `/api/auth/login` | Verify credentials → token + user |
| GET | `/api/auth/me` | Current user |
| POST | `/api/documents/upload` | Ingest a PDF (SHA-256 deduplicated) |
| GET | `/api/documents` | List ingested documents |
| DELETE | `/api/documents/{id}` | Delete document + its vectors |
| POST | `/api/code/ingest-git` | Shallow-clone and index a public repo |
| POST | `/api/code/upload-zip` | Upload and index a repo `.zip` |
| GET | `/api/code/repos` | List indexed repositories |
| DELETE | `/api/code/repos/{id}` | Delete repository + its vectors |
| POST | `/api/query` | Ask a question (documents or code) with retrieval controls |
| POST | `/api/evaluate` | Run a RAG Triad benchmark on a query |
| GET | `/health` | Readiness probe (checks database reachability) |

Interactive Swagger docs are at [`/docs`](http://localhost:8000/docs).

## Project structure

```
.
├── backend/                  # FastAPI service
│   ├── app/
│   │   ├── main.py           # App factory, CORS, lifespan, /health
│   │   ├── config.py         # pydantic-settings (env + .env)
│   │   ├── api/routes/       # auth · documents · code · query · evaluation
│   │   ├── models/           # SQLModel tables + Pydantic API schemas
│   │   └── services/         # ingestion, chunking, embedding, retrieval,
│   │                         # reranking, LLM, evaluation, auth, blob store
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── .env.example
├── frontend/                 # Next.js app
│   ├── app/                  # Landing, auth, dashboard, query, repos, evaluate
│   ├── app/api/upload/       # Vercel Blob client-upload token route
│   ├── components/           # AppShell, Logo, auth shell, UI primitives
│   ├── lib/                  # api client, auth context, types
│   └── Dockerfile
├── docker-compose.yml        # Postgres + backend + frontend (local full stack)
├── render.yaml               # Backend deploy config (Render)
└── backend/vercel.json       # Backend serverless config (Vercel)
```

## Deployment

- **Backend**: deploy via `render.yaml` (Render) or `backend/vercel.json` (Vercel serverless). On hosts with ephemeral disks, point `CHROMA_HOST`/`CHROMA_API_KEY` at Chroma Cloud and set `DATABASE_URL` to a managed Postgres (Supabase, Neon) — local `chroma_data/` and `contexthub.db` do not persist.
- **Frontend**: deploy to Vercel. Set `NEXT_PUBLIC_API_URL` to the backend URL, and `SECRET_KEY` + `BLOB_READ_WRITE_TOKEN` for the `/api/upload` route.
- **CORS**: set `CORS_ORIGINS` on the backend to the exact frontend origin(s).

## License

See repository for license details.
