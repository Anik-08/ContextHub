from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class DocumentRecord(BaseModel):
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
    documents: list[DocumentRecord]
    total: int


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    chunk_count: int
    already_existed: bool = False
    message: str


class BlobIngestRequest(BaseModel):
    blob_url: str = Field(..., description="Vercel Blob URL of the uploaded file.")
    filename: str = Field(..., description="Original filename (used for metadata/citations).")


class DeleteDocumentResponse(BaseModel):
    document_id: str
    message: str


class QueryRequest(BaseModel):
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
    content: str
    page_number: int
    document_id: str
    filename: str
    score: float
    bm25_score: Optional[float] = None
    rrf_score: Optional[float] = None
    rerank_score: Optional[float] = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    question: str


class RepoIngestGitRequest(BaseModel):
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
    repos: list[RepoResponse]
    total: int


class DeleteRepoResponse(BaseModel):
    repo_id: str
    message: str


class CodeSourceChunk(BaseModel):
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
    answer: str
    sources: list[CodeSourceChunk]
    question: str
    repo_id: str


class EvaluationRequest(BaseModel):
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
