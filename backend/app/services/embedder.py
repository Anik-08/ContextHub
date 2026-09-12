"""
embedder.py — Convert text into embedding vectors using ChromaDB's ONNX MiniLM.

WHY ONNX INSTEAD OF sentence-transformers / PyTorch?
  Both produce identical vectors — it is the SAME model (all-MiniLM-L6-v2,
  384-dim), exported to ONNX. The difference is memory:
    - sentence-transformers launches PyTorch + tokenizers (~300-500MB RSS).
    - ONNX Runtime runs the same model in ~100-150MB.
  On hosts with 512MB RAM (Render free tier, Koyeb free, etc.) PyTorch alone
  can OOM the service at boot or first query. ONNX fits comfortably.

  This is why the embedding model is also loaded LAZILY (on first use), never
  at module import time.

HOW SIMILARITY SEARCH WORKS:
  We embed the query with the SAME model used for stored chunks, then ChromaDB
  computes cosine distance between the query vector and every chunk vector.

  ALWAYS embed documents and queries with the SAME model — different models
  produce incompatible vector spaces.
"""

from app.config import settings


# ---------------------------------------------------------------------------
# Lazy singleton model loading
# ---------------------------------------------------------------------------
# Note: chromadb (and with it onnxruntime) must NOT be imported at module
# import — that spike alone can exceed 512MB during boot. Everything heavy is
# deferred until the first embed call.
_embedder = None


def _get_embedder():
    """Load (once) the ONNX MiniLM embedding function used by Chroma itself."""
    global _embedder
    if _embedder is None:
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

        print(f"Loading embedding model: {settings.embedding_model}...")
        # DefaultEmbeddingFunction hardcodes all-MiniLM-L6-v2 (our default) and
        # bundles an ONNX Runtime session — no PyTorch needed for embeddings.
        _embedder = DefaultEmbeddingFunction()
        print("Embedding model loaded.")
    return _embedder


def _normalize(raw):
    """Turn whatever numpy/list the embedder returned into a plain list of floats."""
    import numpy as np

    return np.asarray(raw).tolist()


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a list of texts (used during document ingestion).

    Batching the whole list is far more efficient than looping one at a time.

    Args:
        texts: list of chunk strings to embed

    Returns:
        list of embedding vectors (each a list of floats, length = embedding dim).
    """
    return _normalize(_get_embedder().embed_query(texts))


def embed_query(query: str) -> list[float]:
    """
    Generate an embedding for a single query string (retrieval time).
    Uses the same model as embed_texts() — that consistency is essential.

    Args:
        query: the user's question string

    Returns:
        A single embedding vector (list of floats).
    """
    # embed_query() iterates a bare string character-by-character, so a single
    # query must be wrapped in a one-element list.
    return _normalize(_get_embedder().embed_query([query]))[0]


def get_embedding_dimension() -> int:
    """
    Return the dimensionality of the embeddings currently in use.

    ChromaDB needs the dimension when creating a collection. We derive it
    dynamically (embed a dummy string and measure) instead of hardcoding 384.
    """
    return len(embed_query("test"))


def get_embedding_model():
    """
    Compatibility accessor returning the underlying ONNX embedder.
    Kept so callers that introspect the model still work after the
    torch → ONNX switch.
    """
    return _get_embedder()