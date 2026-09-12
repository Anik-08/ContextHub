"""
embedder.py — Convert text into embedding vectors using sentence-transformers.

WHAT IS AN EMBEDDING?
  An embedding is a list of floating-point numbers (a vector) that represents
  the semantic meaning of text. For example, all-MiniLM-L6-v2 produces 384-dimensional
  embeddings — each piece of text becomes a list of 384 floats.
  
  The key property: texts with similar meanings produce vectors that are close
  together in 384-dimensional space. "Leave policy" and "vacation entitlement"
  will be much closer to each other than "leave policy" and "quarterly revenue".

HOW SIMILARITY SEARCH WORKS:
  When a user asks "What is the leave policy?", we embed that question → get a
  query vector. ChromaDB then computes the distance between the query vector and
  every stored chunk vector. The chunks with the smallest distance (= most similar
  meaning) are returned. This is approximate nearest neighbor (ANN) search.

  Distance metric used by ChromaDB default: L2 (Euclidean distance).
  We'll configure it to use cosine similarity, which is better for text:
    - L2 distance is affected by vector magnitude (length of text).
    - Cosine similarity only measures the angle between vectors → pure semantic similarity.

WHY THE SAME MODEL FOR DOCUMENTS AND QUERIES?
  This is critical. An embedding model maps text into a specific vector space.
  Different models create different spaces — completely incompatible.
  If you embed documents with model A and queries with model B:
    - The vectors live in different spaces.
    - "Close" in space A has no meaning in space B.
    - All your similarity scores would be garbage.
  
  Always embed documents and queries with the SAME model.

WHY sentence-transformers / all-MiniLM-L6-v2?
  - Free, no API key, runs on CPU (important for local development).
  - Small model: ~80MB. Downloads once and is cached on disk.
  - Good quality for a free model.
  - 384 dimensions: compact, fast to search.
  
  Alternatives:
  - OpenAI text-embedding-ada-002: 1536-dim, highest quality, $0.0001/1K tokens
  - OpenAI text-embedding-3-small: better than ada-002, cheaper
  - Cohere embed-v3: excellent for RAG, multilingual
  - BAAI/bge-large-en-v1.5: open-source, near-OpenAI quality, larger/slower
  
  For production RAG, OpenAI or Cohere embeddings often outperform local models.
  V1: we start local to eliminate API cost and internet dependency.

SINGLETON PATTERN:
  Loading the embedding model takes ~2-3 seconds and ~80MB of RAM.
  We load it ONCE at module import time and reuse it for every request.
  This is the standard pattern for ML models in a web service.

Interview angle:
  "What is cosine similarity and why is it used for text embeddings?"
  Answer: Cosine similarity = dot product of two vectors divided by the product
  of their magnitudes. It measures the angle between vectors, ignoring magnitude.
  For text embeddings, the magnitude can vary with text length, but the direction
  (semantic meaning) is what matters. Cosine similarity isolates direction → angle.
  
  "What are the dimensions in an embedding? What does each one represent?"
  Answer: The dimensions don't have human-interpretable meanings — they're learned
  by the neural network during training. Each dimension is a learned feature.
  The geometry of the overall space is what encodes meaning.
"""

from app.config import settings


# ---------------------------------------------------------------------------
# Lazy singleton model loading
# ---------------------------------------------------------------------------
# The model is loaded on FIRST USE, not at module import. Importing this module
# must stay cheap: sentence-transformers pulls in PyTorch (~200MB+ RSS), which
# would OOM low-memory hosts (e.g. Render free tier, 512MB) at boot time.
# After the first call the module-level cache is reused for every request.
_model = None


def get_embedding_model():
    """Load the sentence-transformer model on demand and return the cached instance."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        print(f"Loading embedding model: {settings.embedding_model}...")
        _model = SentenceTransformer(settings.embedding_model)
        print("Embedding model loaded.")
    return _model


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a list of texts (used during document ingestion).

    We pass a whole list (batch) at once rather than one text at a time.
    Why? sentence-transformers processes batches efficiently using matrix
    operations on the CPU/GPU. Batching is typically 5-10x faster than
    looping over individual texts.

    Args:
        texts: list of strings to embed (chunk texts from the chunker)

    Returns:
        list of embedding vectors, one per input text.
        Each vector is a list of floats (length = embedding dimension).
        
        Example for all-MiniLM-L6-v2:
        [
            [0.021, -0.134, 0.872, ...],  # 384 floats for texts[0]
            [0.093, -0.021, 0.341, ...],  # 384 floats for texts[1]
            ...
        ]
    """
    # encode() returns a numpy array of shape (len(texts), embedding_dim).
    # .tolist() converts it to a plain Python list of lists — required by ChromaDB.
    # show_progress_bar=False: don't print progress for every API request (noisy).
    model = get_embedding_model()
    embeddings = model.encode(texts, show_progress_bar=False)
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    """
    Generate an embedding for a single query string (used at retrieval time).

    This is separated from embed_texts() to make the intent clear:
      - embed_texts() is for bulk ingestion (many chunks at once)
      - embed_query() is for a single question at query time
    
    Under the hood they use the same model — just a convenience separation.

    Args:
        query: the user's question string

    Returns:
        A single embedding vector (list of floats).
    """
    # encode() handles a single string too — returns shape (embedding_dim,).
    model = get_embedding_model()
    embedding = model.encode(query, show_progress_bar=False)
    return embedding.tolist()


def get_embedding_dimension() -> int:
    """
    Return the dimensionality of the embeddings produced by the current model.
    
    ChromaDB needs to know the dimension when you create a collection.
    This function lets us get it dynamically rather than hardcoding 384.
    If we switch embedding models, this automatically returns the right value.
    """
    # Embed a dummy string and measure its length
    model = get_embedding_model()
    dummy = model.encode("test")
    return len(dummy)
