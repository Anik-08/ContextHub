"""
query.py — API route for asking questions about uploaded documents.

ENDPOINT: POST /api/query

V2 ENHANCEMENTS:
  - Supports `document_id` in QueryRequest.
  - When provided, retrieval is strictly scoped to that document's chunks.
  - When omitted (None), retrieval searches across the entire knowledge base.

GROUNDED GENERATION:
  We return both the answer and the exact source chunks with similarity scores.
  This allows UI verification and transparent auditing of model citations.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas import QueryRequest, QueryResponse, SourceChunk
from app.models.db_models import User
from app.services.auth_deps import get_current_user
from app.services.rag_pipeline import query_rag
from app.services.document_registry import get_document_by_id


router = APIRouter(prefix="/api", tags=["Query"])


@router.post(
    "/query",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a question about uploaded documents",
    description=(
        "Submit a natural-language question. The system retrieves relevant document "
        "chunks from ChromaDB (optionally filtered by document_id) and uses Groq LLM "
        "to generate a grounded answer with page citations."
    ),
)
async def query_documents(
    request: QueryRequest,
    user: User = Depends(get_current_user),
) -> QueryResponse:
    # Multi-tenant access control: a user may only query documents they own.
    # If a document_id is given and it isn't theirs, treat it as not found —
    # otherwise guesting another user's UUID would let you reach their content.
    if request.document_id and not get_document_by_id(request.document_id, user.user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{request.document_id}' not found.",
        )

    try:
        result = query_rag(
            question=request.question,
            top_k=request.top_k,
            document_id=request.document_id,
            search_mode=request.search_mode,
            enable_rerank=request.enable_rerank,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {str(e)}",
        )

    source_chunks = [
        SourceChunk(
            content=chunk["text"],
            page_number=chunk["page_number"],
            document_id=chunk["document_id"],
            filename=chunk["source"],
            score=chunk.get("score", 0.0),
            bm25_score=chunk.get("bm25_score"),
            rrf_score=chunk.get("rrf_score"),
            rerank_score=chunk.get("rerank_score"),
        )
        for chunk in result["sources"]
    ]

    return QueryResponse(
        answer=result["answer"],
        sources=source_chunks,
        question=result["question"],
    )
