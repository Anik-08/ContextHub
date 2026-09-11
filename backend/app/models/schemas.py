"""
schemas.py — Pydantic models defining the API contracts (requests and responses).

WHAT WE ARE BUILDING:
  We are expanding our Pydantic schemas to support V2 features:
    - Document listing (GET /api/documents)
    - Document deletion response (DELETE /api/documents/{id})
    - Document deduplication signal on upload response
    - Filtered querying by document_id (POST /api/query)

WHY WE NEED IT:
  APIs require strict boundaries. Clients (like Next.js frontend or curl) need
  predictable JSON shapes, type guarantees, and clear status responses.
  Pydantic ensures:
    - Invalid data from clients is rejected early with HTTP 422.
    - Outgoing data is cleanly serialized (e.g. converting Python datetime to ISO-8601 strings).
    - Swagger/OpenAPI documentation (/docs) is automatically generated.

DATA FLOW:
  Client Request (JSON)
       │
       ▼
  FastAPI parses & validates against Pydantic Request Model
       │
       ▼
  Internal Services / Database (SQLModel / ChromaDB)
       │
       ▼
  FastAPI maps results into Pydantic Response Model
       │
       ▼
  Client receives validated JSON

INTERVIEW ANGLE:
  "Why separate database models (SQLModel) from API schemas (Pydantic)?"
  Answer: Even though SQLModel inherits from Pydantic, separating the public API
  schemas from internal database representations provides decoupling. For example,
  you might not want to expose sensitive internal fields (like internal storage paths,
  raw hashes, or soft-delete flags) in every API response. It also allows the database
  schema and API versioning to evolve independently.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Document Models
# ---------------------------------------------------------------------------

class DocumentRecord(BaseModel):
    """
    Representation of an ingested document for listing and inspection.
    """
    document_id: str
    filename: str
    file_hash: str
    file_size_bytes: int
    page_count: int
    chunk_count: int
    title: Optional[str] = None
    author: Optional[str] = None
    uploaded_at: datetime


class DocumentListResponse(BaseModel):
    """
    Response returned by GET /api/documents.
    Contains the list of registered documents and total count.
    """
    documents: list[DocumentRecord]
    total: int


class DocumentUploadResponse(BaseModel):
    """
    Returned after a PDF upload.
    
    already_existed: True if SHA-256 deduplication caught an existing file,
                     skipping redundant chunking and embedding.
    """
    document_id: str
    filename: str
    chunk_count: int
    already_existed: bool = False
    message: str


class DeleteDocumentResponse(BaseModel):
    """
    Returned after deleting a document and its vector chunks.
    """
    document_id: str
    message: str


# ---------------------------------------------------------------------------
# Query Models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    """
    Request body for asking questions.
    """
    question: str = Field(
        ...,
        min_length=3,
        description="The question to answer using the uploaded documents.",
        examples=["What is the leave policy?"],
    )
    top_k: Optional[int] = Field(
        default=None,
        ge=1,
        le=20,
        description="Number of document chunks to retrieve. Defaults to server setting.",
    )
    document_id: Optional[str] = Field(
        default=None,
        description="Optional document_id to restrict the search scope to a specific document.",
    )
    search_mode: str = Field(
        default="hybrid",
        description="Retrieval mode: 'hybrid' (dense+sparse), 'dense' (vector only), or 'sparse' (BM25 only).",
    )
    enable_rerank: bool = Field(
        default=True,
        description="Whether to run Cross-Encoder reranking on retrieved candidate chunks.",
    )


class SourceChunk(BaseModel):
    """
    A single retrieved chunk cited as evidence for the LLM's answer.
    """
    content: str
    page_number: int
    document_id: str
    filename: str
    score: float
    bm25_score: Optional[float] = None
    rrf_score: Optional[float] = None
    rerank_score: Optional[float] = None


class QueryResponse(BaseModel):
    """
    Full grounded response from the RAG pipeline.
    """
    answer: str
    sources: list[SourceChunk]
    question: str


# ---------------------------------------------------------------------------
# Codebase RAG Models (V3 & V4)
# ---------------------------------------------------------------------------

class RepoIngestGitRequest(BaseModel):
    """
    Request to clone and index a Git repository from a public URL.
    """
    git_url: str = Field(
        ...,
        description="Public Git repository URL (HTTPS).",
        examples=["https://github.com/encode/starlette"],
    )
    branch: Optional[str] = Field(
        default=None,
        description="Optional Git branch name. If omitted, default branch is cloned.",
    )


class RepoResponse(BaseModel):
    """
    Represents an indexed repository record.
    """
    repo_id: str
    name: str
    clone_url: Optional[str] = None
    commit_hash: Optional[str] = None
    file_count: int
    chunk_count: int
    primary_language: Optional[str] = None
    created_at: datetime
    message: Optional[str] = None


class RepoListResponse(BaseModel):
    """
    Response listing all indexed repositories.
    """
    repos: list[RepoResponse]
    total: int


class DeleteRepoResponse(BaseModel):
    """
    Confirmation of repository deletion.
    """
    repo_id: str
    message: str


class CodeSourceChunk(BaseModel):
    """
    Source code snippet returned as evidence for an answer.
    """
    content: str
    file_path: str
    start_line: int
    end_line: int
    language: str
    repo_id: str
    score: float
    bm25_score: Optional[float] = None
    rrf_score: Optional[float] = None
    rerank_score: Optional[float] = None


class CodeQueryRequest(BaseModel):
    """
    Request for asking code intelligence questions.
    """
    question: str = Field(
        ...,
        min_length=3,
        description="Question about the codebase (e.g. 'Where is auth implemented?').",
        examples=["Where is user authentication handled in this codebase?"],
    )
    repo_id: str = Field(
        ...,
        description="ID of the repository to query.",
    )
    path_filter: Optional[str] = Field(
        default=None,
        description="Optional path prefix filter (e.g. 'src/auth' or 'backend').",
    )
    top_k: Optional[int] = Field(
        default=None,
        ge=1,
        le=20,
        description="Number of code chunks to retrieve. Defaults to 5.",
    )
    search_mode: str = Field(
        default="hybrid",
        description="Retrieval mode: 'hybrid', 'dense', or 'sparse'.",
    )
    enable_rerank: bool = Field(
        default=True,
        description="Whether to run Cross-Encoder reranking.",
    )


class CodeQueryResponse(BaseModel):
    """
    Answer to a code question with file and line range citations.
    """
    answer: str
    sources: list[CodeSourceChunk]
    question: str
    repo_id: str


# ---------------------------------------------------------------------------
# Evaluation Models (V4)
# ---------------------------------------------------------------------------

class EvaluationRequest(BaseModel):
    """
    Request to run an automated RAG Triad benchmark evaluation.
    """
    question: str = Field(
        ...,
        description="The test question to evaluate.",
        examples=["What is the company leave policy?"],
    )
    document_id: Optional[str] = Field(
        default=None,
        description="Optional document ID if testing document RAG.",
    )
    repo_id: Optional[str] = Field(
        default=None,
        description="Optional repo ID if testing code RAG.",
    )
    search_mode: str = Field(
        default="hybrid",
        description="Retrieval mode to benchmark: 'hybrid', 'dense', or 'sparse'.",
    )
    enable_rerank: bool = Field(
        default=True,
        description="Whether to enable Cross-Encoder reranking during the benchmark.",
    )


class EvaluationResponse(BaseModel):
    """
    Quantitative benchmark result across the RAG Triad.
    """
    question: str
    answer: str
    context_relevance_score: float = Field(
        ...,
        description="0.0 to 1.0 score of retrieved context relevance to the question.",
    )
    context_relevance_reason: str
    faithfulness_score: float = Field(
        ...,
        description="0.0 to 1.0 score of answer groundedness in context (hallucination check).",
    )
    faithfulness_reason: str
    answer_relevance_score: float = Field(
        ...,
        description="0.0 to 1.0 score of how directly the answer addresses the question.",
    )
    answer_relevance_reason: str
    composite_score: float = Field(
        ...,
        description="Average Triad score across all three dimensions.",
    )
    retrieved_sources_count: int


