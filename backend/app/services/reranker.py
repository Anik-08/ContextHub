"""
reranker.py — Two-stage retrieval Cross-Encoder reranking module.

WHAT WE ARE BUILDING:
  A Cross-Encoder reranker that re-scores candidate chunks retrieved from
  Stage 1 (Hybrid Dense + Sparse search).

THE FUNDAMENTAL DIFFERENCE: BI-ENCODER vs CROSS-ENCODER:

1. Bi-Encoder (Stage 1 / Ingestion & Fast Retrieval):
   - Architecture:
       Query -> Transformer -> Vector A (384-dim)
       Chunk -> Transformer -> Vector B (384-dim)
       Similarity = dot_product(Vector A, Vector B)
   - Advantage: Extremely fast. Vectors are pre-computed at ingestion time.
     Searching 100,000 vectors takes 2 milliseconds with HNSW indexing.
   - Disadvantage: Information loss. Compressing 1,000 characters into a single
     fixed-size 384-float vector creates a bottleneck. No token-level interaction
     between the query words and the chunk words.

2. Cross-Encoder (Stage 2 / Re-scoring):
   - Architecture:
       Input: [CLS] Query [SEP] Document Chunk [SEP]
       All tokens pass together through all 6 transformer layers.
   - Advantage: Full cross-attention! Every token in the query attends to every token
     in the document. It understands negation, word order, modifier attachment,
     and semantic alignment at the token level.
   - Disadvantage: Slow. Cannot pre-compute vectors because the input depends on the query.
     Running it across 100,000 documents would take 30+ seconds.

THE TWO-STAGE RETRIEVAL PATTERN (INDUSTRY STANDARD):
  1. Stage 1 (High Recall):
     Hybrid search (Dense + BM25) quickly narrows 10,000 chunks down to 20 candidates (~15ms).
  2. Stage 2 (High Precision):
     Cross-Encoder re-scores those 20 candidates to find the true top 5 (~25ms).
  Result: Sub-50ms total latency with the accuracy of full cross-attention.

MODEL USED:
  `cross-encoder/ms-marco-MiniLM-L-6-v2`
  - Compact (80MB), fast CPU inference.
  - Pre-trained on Microsoft MARCO (500,000 real search queries with human annotations).

INTERVIEW ANGLE:
  "Why do RAG systems need a reranker if they already use vector databases?"
  Answer:
    Bi-encoder embeddings suffer from the 'embedding bottleneck'—they compress complex
    passages into single vectors, leading to false positives in the top 5 results.
    A reranker provides a second opinion using cross-attention, boosting MRR
    (Mean Reciprocal Rank) and NDCG@5 by 15-35% in benchmark evaluations.
"""

from typing import Optional
from sentence_transformers import CrossEncoder


# Model name for fast CPU passage reranking
RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_reranker: Optional[CrossEncoder] = None


def get_reranker() -> Optional[CrossEncoder]:
    """
    Lazy load CrossEncoder singleton.
    Lazy loading ensures the app starts quickly and only loads the model on demand.
    """
    global _reranker
    if _reranker is None:
        try:
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
    """
    Re-score candidate chunks using cross-attention against the query.

    Args:
        query: The user's question or search query.
        chunks: Top candidate chunks from Stage 1 (Hybrid Search).
        top_k: Desired number of final results after reranking.

    Returns:
        Top-k chunks sorted by cross-encoder score descending, with 'rerank_score' added.
    """
    if not chunks:
        return []

    # If there are fewer or equal chunks than top_k and no reranker is loaded, return as-is
    reranker = get_reranker()
    if reranker is None:
        return chunks[:top_k]

    # Prepare (query, text) pairs for the cross-encoder
    sentence_pairs = [[query, chunk["text"]] for chunk in chunks]

    # Predict cross-encoder scores (higher = more relevant)
    # The output is raw logits; higher indicates stronger semantic alignment
    try:
        scores = reranker.predict(sentence_pairs)
    except Exception as e:
        print(f"[Reranker] Prediction error: {e}. Returning unranked chunks.")
        return chunks[:top_k]

    # Attach rerank_score to each chunk
    scored_chunks = []
    for chunk, score in zip(chunks, scores):
        scored_chunks.append({
            **chunk,
            "rerank_score": round(float(score), 4),
        })

    # Sort descending by cross-encoder score
    scored_chunks.sort(key=lambda x: x["rerank_score"], reverse=True)

    return scored_chunks[:top_k]
