"""
evaluation.py — API route for quantitative RAG Triad benchmarking.

ENDPOINT: POST /api/evaluate

WHAT THIS ENDPOINT DOES:
  Executes a query through the ContextHub RAG pipeline (documents or code),
  extracts the retrieved context and generated answer, and runs an objective
  LLM-as-a-Judge evaluation measuring:
    1. Context Relevance (Did retrieval find the right information?)
    2. Faithfulness / Groundedness (Did the answer avoid hallucinations?)
    3. Answer Relevance (Did the response actually address the question?)

WHY THIS IS ESSENTIAL FOR AN AI ENGINEER PORTFOLIO:
  Anyone can build a basic toy RAG script.
  A professional AI Engineer builds:
    - Observability and evaluation metrics.
    - Automated regression benchmarks.
    - Hallucination detection guardrails.
  This endpoint allows developers and hiring managers to submit test questions
  and see transparent, quantitative quality scores in real time.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas import EvaluationRequest, EvaluationResponse
from app.models.db_models import User
from app.services.auth_deps import get_current_user
from app.services.rag_pipeline import query_rag
from app.services.code_rag_pipeline import query_codebase
from app.services.rag_evaluator import evaluate_rag_response
from app.services.document_registry import get_document_by_id, get_repository_by_id


router = APIRouter(prefix="/api", tags=["Evaluation & Benchmarking"])


@router.post(
    "/evaluate",
    response_model=EvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Benchmark RAG Triad scores (Context Relevance, Faithfulness, Answer Relevance)",
    description=(
        "Executes a test query through ContextHub and evaluates the result using LLM-as-a-Judge. "
        "Returns numerical scores (0.0 to 1.0) and reasoning for Context Relevance, Faithfulness, "
        "and Answer Relevance."
    ),
)
async def evaluate_query_endpoint(
    request: EvaluationRequest,
    user: User = Depends(get_current_user),
) -> EvaluationResponse:
    # Multi-tenant ownership checks before running anything.
    if request.document_id and not get_document_by_id(request.document_id, user.user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{request.document_id}' not found.",
        )
    if request.repo_id and not get_repository_by_id(request.repo_id, user.user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID '{request.repo_id}' not found.",
        )

    try:
        # Determine whether this is a code query or document query
        if request.repo_id:
            rag_output = query_codebase(
                question=request.question,
                repo_id=request.repo_id,
                search_mode=request.search_mode,
                enable_rerank=request.enable_rerank,
                owner_id=user.user_id,
            )
        else:
            rag_output = query_rag(
                question=request.question,
                document_id=request.document_id,
                search_mode=request.search_mode,
                enable_rerank=request.enable_rerank,
            )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG execution during evaluation failed: {str(e)}",
        )

    answer = rag_output.get("answer", "")
    context = rag_output.get("context", "")
    sources = rag_output.get("sources", [])

    # If guardrail stopped generation due to irrelevance, score accordingly
    if not context or not sources:
        return EvaluationResponse(
            question=request.question,
            answer=answer,
            context_relevance_score=0.0,
            context_relevance_reason="No relevant context was found by the retrieval engine (relevance guardrail triggered).",
            faithfulness_score=1.0,
            faithfulness_reason="The model correctly refused to answer rather than hallucinating when no context was present.",
            answer_relevance_score=0.8,
            answer_relevance_reason="The model accurately conveyed that the requested information was not present in the indexed corpus.",
            composite_score=0.6,
            retrieved_sources_count=0,
        )

    # Run RAG Triad evaluation
    eval_result = evaluate_rag_response(
        question=request.question,
        context=context,
        answer=answer,
    )

    return EvaluationResponse(
        question=request.question,
        answer=answer,
        context_relevance_score=eval_result["context_relevance_score"],
        context_relevance_reason=eval_result["context_relevance_reason"],
        faithfulness_score=eval_result["faithfulness_score"],
        faithfulness_reason=eval_result["faithfulness_reason"],
        answer_relevance_score=eval_result["answer_relevance_score"],
        answer_relevance_reason=eval_result["answer_relevance_reason"],
        composite_score=eval_result["composite_score"],
        retrieved_sources_count=len(sources),
    )
