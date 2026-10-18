from typing import Optional

from app.services.embedder import embed_query
from app.services.vector_store import query_chunks, get_collection
from app.services.code_vector_store import query_code_chunks, get_code_collection
from app.services.bm25_indexer import get_or_build_bm25_index
from app.services.reranker import rerank_chunks


RRF_K = 60
CANDIDATE_POOL_SIZE = 20


def reciprocal_rank_fusion(
    dense_results: list[dict],
    sparse_results: list[dict],
    top_k: int = 10,
) -> list[dict]:
    fused: dict[str, dict] = {}
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

    merged_list = list(fused.values())
    merged_list.sort(key=lambda x: x["rrf_score"], reverse=True)
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
    if search_mode == "sparse":
        sparse_candidates = _get_document_bm25_results(query, document_id, top_k=top_k)
        if enable_rerank:
            return rerank_chunks(query, sparse_candidates, top_k=top_k)
        return sparse_candidates[:top_k]

    if search_mode == "dense":
        query_vector = embed_query(query)
        dense_candidates = query_chunks(query_vector, top_k=CANDIDATE_POOL_SIZE if enable_rerank else top_k, document_id=document_id)
        if enable_rerank:
            return rerank_chunks(query, dense_candidates, top_k=top_k)
        return dense_candidates[:top_k]

    query_vector = embed_query(query)
    dense_candidates = query_chunks(query_vector, top_k=CANDIDATE_POOL_SIZE, document_id=document_id)
    sparse_candidates = _get_document_bm25_results(query, document_id, top_k=CANDIDATE_POOL_SIZE)
    fused_candidates = reciprocal_rank_fusion(dense_candidates, sparse_candidates, top_k=CANDIDATE_POOL_SIZE)
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

    query_vector = embed_query(query)
    dense_candidates = query_code_chunks(query_vector, top_k=CANDIDATE_POOL_SIZE, repo_id=repo_id, path_filter=path_filter)
    sparse_candidates = _get_code_bm25_results(query, repo_id, path_filter, top_k=CANDIDATE_POOL_SIZE)
    fused_candidates = reciprocal_rank_fusion(dense_candidates, sparse_candidates, top_k=CANDIDATE_POOL_SIZE)
    if enable_rerank:
        final_results = rerank_chunks(query, fused_candidates, top_k=top_k)
    else:
        final_results = fused_candidates[:top_k]

    return final_results


def _get_document_bm25_results(query: str, document_id: Optional[str], top_k: int) -> list[dict]:
    collection = get_collection()
    where = {"document_id": document_id} if document_id else None
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
