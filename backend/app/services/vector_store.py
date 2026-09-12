"""
vector_store.py — ChromaDB wrapper: store and retrieve document chunks + embeddings.

WHAT IS A VECTOR DATABASE?
  A regular database (PostgreSQL) stores rows and lets you filter by exact values:
    SELECT * FROM docs WHERE page = 4
  
  A vector database stores embedding vectors alongside data and lets you search
  by semantic similarity:
    "Give me the 5 rows whose vectors are most similar to this query vector"
  
  This is called Approximate Nearest Neighbor (ANN) search. It's approximate
  because exact nearest neighbor in high dimensions is prohibitively expensive
  (curse of dimensionality). ANN trades a tiny bit of recall for massive speed gains.

WHY CHROMADB FOR V1?
  - Zero infrastructure: runs in-process, persists to a local directory.
  - No Docker, no cloud account, no connection string.
  - Python-native API.
  - Good enough for tens of thousands of chunks.
  
  When would you outgrow ChromaDB?
  - Millions of vectors → Pinecone, Weaviate, Qdrant (managed, horizontally scalable)
  - Need SQL + vector in same DB → pgvector (PostgreSQL extension) — great for V5
  - Need maximum speed locally → FAISS (Facebook AI Similarity Search), no persistence

HOW CHROMADB STORES DATA:
  ChromaDB organizes data into "collections" (like tables in SQL).
  Each document in a collection has:
    - id:        a unique string identifier
    - embedding: the vector (list of floats)
    - document:  the raw text
    - metadata:  a dict of arbitrary key-value pairs (page_number, source, etc.)
  
  We use a SINGLE collection for all documents in V1.
  In V2, we'll add document_id filtering so users can query one document at a time.

DISTANCE METRIC — COSINE vs L2:
  ChromaDB supports multiple distance metrics:
    - "l2"     (default): Euclidean distance. Sensitive to vector magnitude.
    - "cosine": measures angle between vectors, ignores magnitude. Better for text.
    - "ip"     (inner product): used with certain normalized embeddings.
  
  We use cosine. For text embeddings from sentence-transformers, cosine similarity
  is the standard metric and produces more meaningful similarity scores.

  Note: ChromaDB's cosine metric actually returns cosine DISTANCE = 1 - cosine_similarity.
  So distance 0 = identical, distance 1 = completely unrelated, distance 2 = opposite.
  We convert to similarity (1 - distance) before returning scores to the user.

Interview angle:
  "What is HNSW and why does ChromaDB use it?"
  Answer: HNSW (Hierarchical Navigable Small World) is the ANN index algorithm used
  by ChromaDB (and most vector DBs). It builds a multi-layer graph where each layer
  has progressively fewer nodes. Search starts at the top layer (coarse), descends
  to find the true nearest neighbors. O(log n) search complexity.
  
  "How would you scale a vector database to millions of documents?"
  Answer: Shard across multiple nodes (Qdrant, Weaviate support this natively).
  Or use Pinecone (managed). Or pgvector with partitioning. ChromaDB would be
  replaced at that scale. The chunking and embedding pipeline stays the same.
"""

import socket

import chromadb
from chromadb.config import Settings as ChromaSettings
from app.config import settings


# ---------------------------------------------------------------------------
# Collection name — single collection for all documents in V1
# ---------------------------------------------------------------------------
COLLECTION_NAME = "contexthub_documents"


def _preflight_chroma_connection() -> None:
    """
    Fail fast (instead of hanging) when the remote Chroma server is unreachable.

    chromadb.HttpClient() performs a live request inside its constructor, so a
    misconfigured/silently-dropped endpoint stalls the process for minutes.
    We probe the TCP port with a short timeout first and raise a clear error.
    """
    if not settings.chroma_host:
        return
    try:
        with socket.create_connection(
            (settings.chroma_host, settings.chroma_port), timeout=5
        ):
            pass
    except Exception as e:
        raise ConnectionError(
            f"Cannot reach ChromaDB at {settings.chroma_host}:{settings.chroma_port} "
            f"({e}). Check CHROMA_HOST / CHROMA_PORT / CHROMA_SSL variables."
        ) from e


# ---------------------------------------------------------------------------
# ChromaDB client factory — supports local (PersistentClient) AND remote
# (HttpClient, e.g. Chroma Cloud / self-hosted chroma server).
#
# IMPORTANT: the client is built LAZILY (on first vector operation), never at
# module import. chromadb.HttpClient() connects to the server in its
# constructor, so connecting at import time stalls app boot on low-connectivity /
# slow hosts — which looks like "no open ports detected" on Render.
#
# anonymized_telemetry=False: opt out of ChromaDB's telemetry data collection.
# ---------------------------------------------------------------------------
def get_chroma_client():
    kwargs: dict = {"settings": ChromaSettings(anonymized_telemetry=False)}
    if settings.chroma_host:
        _preflight_chroma_connection()
        kwargs.update(
            host=settings.chroma_host,
            port=settings.chroma_port,
            ssl=settings.chroma_ssl,
        )
        if settings.chroma_api_key:
            # Chroma Cloud authenticates with an X-Chroma-Token header.
            kwargs.setdefault("headers", {}).update(
                {"X-Chroma-Token": settings.chroma_api_key}
            )
        if settings.chroma_tenant:
            kwargs["tenant"] = settings.chroma_tenant
        if settings.chroma_database:
            kwargs["database"] = settings.chroma_database
        return chromadb.HttpClient(**kwargs)
    return chromadb.PersistentClient(
        path=settings.chroma_persist_dir,
        **kwargs,
    )


_client: object | None = None


def get_client():
    """Return the ChromaDB client, constructing it lazily on first use."""
    global _client
    if _client is None:
        _client = get_chroma_client()
    return _client


def get_collection():
    """
    Get (or create) the ChromaDB collection.
    
    get_or_create_collection() is idempotent — safe to call on every startup.
    If the collection exists (from a previous run), it returns the existing one.
    If not, it creates it fresh.
    
    metadata={"hnsw:space": "cosine"}: tells the HNSW index to use cosine distance.
    This must be set at collection creation time — you can't change it later.
    """
    return get_client().get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},  # use cosine similarity, not L2
    )


# ---------------------------------------------------------------------------
# Ingestion — add chunks to the vector store
# ---------------------------------------------------------------------------

def add_chunks(chunks: list[dict], embeddings: list[list[float]]) -> int:
    """
    Store chunks and their embeddings in ChromaDB.

    Args:
        chunks:     list of chunk dicts from chunker.py
                    each has: text, page_number, source, document_id, chunk_index
        embeddings: list of embedding vectors from embedder.py
                    must be same length as chunks (parallel arrays)

    Returns:
        Number of chunks successfully stored.

    ChromaDB's add() function takes parallel lists:
        ids:        unique string IDs for each document
        embeddings: the vectors
        documents:  the raw text (ChromaDB stores this alongside the vector)
        metadatas:  list of metadata dicts

    All lists must be the same length.
    """
    collection = get_collection()

    # Build parallel lists from our chunk dicts
    ids = []
    documents = []
    metadatas = []

    for i, chunk in enumerate(chunks):
        # Unique ID for each chunk: "{document_id}_chunk_{chunk_index}"
        # This ensures IDs are stable and don't collide across documents.
        chunk_id = f"{chunk['document_id']}_chunk_{chunk['chunk_index']}"
        ids.append(chunk_id)

        documents.append(chunk["text"])

        # Metadata: ChromaDB stores this as-is. We can filter by these fields later.
        # Important: ChromaDB metadata values must be str, int, float, or bool.
        # No nested dicts or lists.
        metadatas.append({
            "page_number": chunk["page_number"],
            "source": chunk["source"],
            "document_id": chunk["document_id"],
            "chunk_index": chunk["chunk_index"],
        })

    # upsert() instead of add(): if a chunk with the same ID already exists,
    # it updates it instead of raising an error. Safer for re-uploads.
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )

    return len(chunks)


# ---------------------------------------------------------------------------
# Retrieval — find the most relevant chunks for a query
# ---------------------------------------------------------------------------

def query_chunks(
    query_embedding: list[float],
    top_k: int,
    document_id: str | None = None,
) -> list[dict]:
    """
    Find the top-k most relevant chunks for a given query embedding.

    Args:
        query_embedding: the embedding vector of the user's question
        top_k:           how many chunks to retrieve
        document_id:     (V2) optional — if set, only search chunks from this document.
                         None = search across ALL uploaded documents.

    Returns:
        list of result dicts, sorted by relevance (most relevant first).

    HOW CHROMADB `where` FILTERS WORK:
      ChromaDB supports MongoDB-style metadata filters.
      {"document_id": "abc-123"} → only consider chunks where metadata["document_id"] == "abc-123"
      This is "pre-filtering": narrow candidates BEFORE computing similarity.
      More efficient than post-filtering (compute all similarities, then discard).

    Interview angle: "How do you implement filtered vector search?"
      Answer: Most vector DBs support metadata filters alongside ANN search.
      The filter pre-screens candidates, then similarity is computed on the subset.
    """
    collection = get_collection()

    count = collection.count()
    if count == 0:
        return []

    actual_top_k = min(top_k, count)

    # Build query kwargs — only add `where` if filtering by document
    query_kwargs: dict = dict(
        query_embeddings=[query_embedding],
        n_results=actual_top_k,
        include=["documents", "metadatas", "distances"],
    )
    if document_id:
        query_kwargs["where"] = {"document_id": document_id}

    results = collection.query(**query_kwargs)

    # Unpack from batch format (results["documents"] is a list-of-lists)
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    # ChromaDB cosine distance = 1 - cosine_similarity → convert to similarity
    retrieved = []
    for doc, meta, distance in zip(documents, metadatas, distances):
        retrieved.append({
            "text": doc,
            "page_number": meta["page_number"],
            "source": meta["source"],
            "document_id": meta["document_id"],
            "score": round(1 - distance, 4),
        })

    return retrieved


def get_document_count() -> int:
    """Return total number of chunks stored in the vector store."""
    return get_collection().count()


def delete_document_chunks(document_id: str) -> None:
    """
    Delete all chunks belonging to a specific document.
    
    Used in V2 for document management (delete a document → remove its chunks).
    ChromaDB supports deletion by metadata filter.
    """
    collection = get_collection()
    collection.delete(where={"document_id": document_id})
