"""
hybrid_retriever.py — Unified Hybrid Retrieval (Dense + Sparse + RRF + Reranking).

WHAT WE ARE BUILDING:
  The central retrieval orchestrator for ContextHub V4.
  It combines:
    1. Dense Vector Search (ChromaDB semantic search).
    2. Sparse Lexical Search (Okapi BM25 keyword matching).
    3. Reciprocal Rank Fusion (RRF) for scale-invariant result merging.
    4. Two-Stage Cross-Encoder Reranking for token-level precision.

HOW RECIPROCAL RANK FUSION (RRF) WORKS:
  Given a set of ranking systems M (e.g. dense vector search and BM25 sparse search),
  the RRF score of document d is defined as:

    RRF_score(d) = sum_{m in M} 1 / (k + rank_m(d))

  where:
    - rank_m(d) is the 1-indexed position of document d in ranking m.
    - k is a smoothing constant (standard value is 60).

WHY RRF INSTEAD OF WEIGHTED SCORE SUM (alpha * dense + (1-alpha) * sparse)?
  1. Cosine similarity is in [0, 1] while BM25 scores are unbounded [0, inf).
     Normalizing BM25 requires estimating min/max scores, which shift wildly
     depending on query length and term rarity.
  2. RRF is rank-based, meaning it cares ONLY about the order of items, not their
     raw score distribution.
  3. Items ranked high in BOTH systems receive an exponential boost.
  4. Parameter-free and battle-tested in search literature (Cormack et al., SIGIR 2009).

THE COMPLETE RETRIEVAL FLOW:
  1. Query: "Where is process_refund defined?"
  2. Fetch top 20 via Dense Vector search.
  3. Fetch top 20 via BM25 Sparse search.
  4. Fuse both lists with RRF -> Top 20 unified candidates.
  5. If reranking enabled:
       Cross-Encoder re-scores top 20 -> Top 5 final results.
  6. Return final ranked chunks with transparent retrieval metadata:
     - dense_score (cosine similarity)
     - bm25_score (if present)
     - rrf_score
     - rerank_score (if reranked)

INTERVIEW ANGLE:
  "Explain Reciprocal Rank Fusion and why it is superior to linear score combination in RAG."
  Answer:
    Linear combination (score_dense + score_sparse) suffers from scale mismatch—BM25
    scores are unbounded and query-dependent, so a single high BM25 score can swamp
    all semantic vector scores. RRF normalizes purely by ranking order:
    1/(60 + rank). It provides a robust, parameter-free combination that naturally
    favors documents appearing near the top of both search modalities.
"""

from typing import Optional

from app.services.embedder import embed_query
from app.services.vector_store import query_chunks, get_collection
from app.services.code_vector_store import query_code_chunks, get_code_collection
from app.services.bm25_indexer import get_or_build_bm25_index
from app.services.reranker import rerank_chunks


RRF_K = 60  # Industry standard smoothing constant
CANDIDATE_POOL_SIZE = 20  # Number of candidates retrieved in Stage 1


def reciprocal_rank_fusion(
    dense_results: list[dict],
    sparse_results: list[dict],
    top_k: int = 10,
) -> list[dict]:
    """
    Merge dense and sparse search results using Reciprocal Rank Fusion (RRF).

    Formula:
      RRF_score = 1 / (60 + dense_rank) + 1 / (60 + sparse_rank)
    """
    # Key chunk by text or unique identifier
    fused: dict[str, dict] = {}

    # 1. Process dense rankings
    for rank, chunk in enumerate(dense_results, start=1):
        key = chunk["text"]
        if key not in fused:
            fused[key] = {
                **chunk,
                "dense_rank": rank,
                "sparse_rank": None,
                "rrf_score": 1.0 / (RRF_K + rank),
            }
        else:
            fused[key]["dense_rank"] = rank
            fused[key]["rrf_score"] += 1.0 / (RRF_K + rank)

    # 2. Process sparse rankings
    for rank, chunk in enumerate(sparse_results, start=1):
        key = chunk["text"]
        if key not in fused:
            fused[key] = {
                **chunk,
                "dense_rank": None,
                "sparse_rank": rank,
                "rrf_score": 1.0 / (RRF_K + rank),
            }
        else:
            fused[key]["sparse_rank"] = rank
            fused[key]["rrf_score"] += 1.0 / (RRF_K + rank)

    # Convert to list and sort descending by rrf_score
    merged_list = list(fused.values())
    merged_list.sort(key=lambda x: x["rrf_score"], reverse=True)

    # Round RRF score for clean display
    for item in merged_list:
        item["rrf_score"] = round(item["rrf_score"], 6)

    return merged_list[:top_k]


def retrieve_document_chunks_v4(
    query: str,
    top_k: int = 5,
    document_id: Optional[str] = None,
    search_mode: str = "hybrid",
    enable_rerank: bool = True,
) -> list[dict]:
    """
    Advanced multi-stage retrieval for PDF documents.

    Modes:
      - 'hybrid': Dense + BM25 + RRF + Cross-Encoder Rerank
      - 'dense': Dense vector similarity only
      - 'sparse': BM25 keyword matching only
    """
    if search_mode == "sparse":
        # Pure BM25 retrieval
        sparse_candidates = _get_document_bm25_results(query, document_id, top_k=top_k)
        if enable_rerank:
            return rerank_chunks(query, sparse_candidates, top_k=top_k)
        return sparse_candidates[:top_k]

    if search_mode == "dense":
        # Pure Vector retrieval
        query_vector = embed_query(query)
        dense_candidates = query_chunks(query_vector, top_k=CANDIDATE_POOL_SIZE if enable_rerank else top_k, document_id=document_id)
        if enable_rerank:
            return rerank_chunks(query, dense_candidates, top_k=top_k)
        return dense_candidates[:top_k]

    # Hybrid Search (Default)
    # Stage 1: Gather top 20 dense and top 20 sparse candidates
    query_vector = embed_query(query)
    dense_candidates = query_chunks(query_vector, top_k=CANDIDATE_POOL_SIZE, document_id=document_id)
    sparse_candidates = _get_document_bm25_results(query, document_id, top_k=CANDIDATE_POOL_SIZE)

    # Reciprocal Rank Fusion
    fused_candidates = reciprocal_rank_fusion(dense_candidates, sparse_candidates, top_k=CANDIDATE_POOL_SIZE)

    # Stage 2: Cross-Encoder Reranking
    if enable_rerank:
        final_results = rerank_chunks(query, fused_candidates, top_k=top_k)
    else:
        final_results = fused_candidates[:top_k]

    return final_results


def retrieve_code_chunks_v4(
    query: str,
    repo_id: str,
    top_k: int = 5,
    path_filter: Optional[str] = None,
    search_mode: str = "hybrid",
    enable_rerank: bool = True,
) -> list[dict]:
    """
    Advanced multi-stage retrieval for source code repositories.
    """
    if search_mode == "sparse":
        sparse_candidates = _get_code_bm25_results(query, repo_id, path_filter, top_k=top_k)
        if enable_rerank:
            return rerank_chunks(query, sparse_candidates, top_k=top_k)
        return sparse_candidates[:top_k]

    if search_mode == "dense":
        query_vector = embed_query(query)
        dense_candidates = query_code_chunks(query_vector, top_k=CANDIDATE_POOL_SIZE if enable_rerank else top_k, repo_id=repo_id, path_filter=path_filter)
        if enable_rerank:
            return rerank_chunks(query, dense_candidates, top_k=top_k)
        return dense_candidates[:top_k]

    # Hybrid Search (Default)
    query_vector = embed_query(query)
    dense_candidates = query_code_chunks(query_vector, top_k=CANDIDATE_POOL_SIZE, repo_id=repo_id, path_filter=path_filter)
    sparse_candidates = _get_code_bm25_results(query, repo_id, path_filter, top_k=CANDIDATE_POOL_SIZE)

    # Reciprocal Rank Fusion
    fused_candidates = reciprocal_rank_fusion(dense_candidates, sparse_candidates, top_k=CANDIDATE_POOL_SIZE)

    # Stage 2: Cross-Encoder Reranking
    if enable_rerank:
        final_results = rerank_chunks(query, fused_candidates, top_k=top_k)
    else:
        final_results = fused_candidates[:top_k]

    return final_results


# ---------------------------------------------------------------------------
# Internal Helpers: Dynamic In-Memory BM25 Loading
# ---------------------------------------------------------------------------

def _get_document_bm25_results(query: str, document_id: Optional[str], top_k: int) -> list[dict]:
    """Load document chunks from ChromaDB into BM25 index on demand and search."""
    collection = get_collection()
    where = {"document_id": document_id} if document_id else None
    
    # Retrieve documents and metadatas for indexing
    raw = collection.get(where=where, include=["documents", "metadatas"])
    if not raw or not raw["documents"]:
        return []

    chunks = []
    for doc, meta in zip(raw["documents"], raw["metadatas"]):
        chunks.append({
            "text": doc,
            "page_number": meta.get("page_number", 1),
            "source": meta.get("source", ""),
            "document_id": meta.get("document_id", ""),
            "score": 0.0,
        })

    cache_key = f"doc:{document_id or 'all'}"
    bm25_index = get_or_build_bm25_index(cache_key, chunks)
    return bm25_index.search(query, top_k=top_k)


def _get_code_bm25_results(query: str, repo_id: str, path_filter: Optional[str], top_k: int) -> list[dict]:
    """Load code chunks from ChromaDB into BM25 index on demand and search."""
    collection = get_code_collection()
    raw = collection.get(where={"repo_id": repo_id}, include=["documents", "metadatas"])
    if not raw or not raw["documents"]:
        return []

    chunks = []
    for doc, meta in zip(raw["documents"], raw["metadatas"]):
        if path_filter and not meta.get("file_path", "").startswith(path_filter):
            continue
        chunks.append({
            "text": doc,
            "file_path": meta.get("file_path", ""),
            "start_line": meta.get("start_line", 1),
            "end_line": meta.get("end_line", 1),
            "language": meta.get("language", ""),
            "repo_id": meta.get("repo_id", repo_id),
            "score": 0.0,
        })

    cache_key = f"repo:{repo_id}"
    bm25_index = get_or_build_bm25_index(cache_key, chunks)
    return bm25_index.search(query, top_k=top_k)
