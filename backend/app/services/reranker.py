from typing import Optional


RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_reranker: Optional[object] = None


def get_reranker():
    global _reranker
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder
            print(f"[Reranker] Loading CrossEncoder model: {RERANKER_MODEL_NAME}...")
            _reranker = CrossEncoder(RERANKER_MODEL_NAME, max_length=512)
            print("[Reranker] CrossEncoder model loaded successfully.")
        except Exception as e:
            print(f"[Reranker] Warning: Could not load CrossEncoder ({e}). Falling back to Stage 1 ranking.")
            _reranker = None
    return _reranker


def rerank_chunks(
    query: str,
    chunks: list[dict],
    top_k: int = 5,
) -> list[dict]:
    if not chunks:
        return []

    reranker = get_reranker()
    if reranker is None:
        return chunks[:top_k]

    sentence_pairs = [[query, chunk["text"]] for chunk in chunks]
    try:
        scores = reranker.predict(sentence_pairs)
    except Exception as e:
        print(f"[Reranker] Prediction error: {e}. Returning unranked chunks.")
        return chunks[:top_k]

    scored_chunks = []
    for chunk, score in zip(chunks, scores):
        scored_chunks.append({
            **chunk,
            "rerank_score": round(float(score), 4),
        })

    scored_chunks.sort(key=lambda x: x["rerank_score"], reverse=True)
    return scored_chunks[:top_k]
