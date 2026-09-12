"""
code_vector_store.py — Vector database wrapper for indexing and querying source code.

WHAT WE ARE BUILDING:
  A dedicated vector store interface for code snippets using ChromaDB.
  It operates on a distinct collection: `contexthub_code`.

WHY A SEPARATE VECTOR COLLECTION FOR CODE?
  1. Preventing Cross-Domain Pollution:
     If general PDF documentation and code snippets live in the same vector index,
     a query like "How does user signup work?" might return random unit tests or
     package.json snippets rather than the intended specification document.
     Segregating collections gives clean domain separation.
  2. Different Metadata Schemas:
     Document chunks have: {page_number, source_pdf, doc_id}.
     Code chunks have: {file_path, start_line, end_line, language, repo_id}.
     Different metadata schemas are much cleaner to manage in dedicated collections.
  3. Independent Lifecycle & Index Tuning:
     Codebases can have 50,000+ chunks with frequent commits, whereas company
     policies are updated rarely. Separate collections allow independent index
     tuning and deletion.

HOW CODE RETRIEVAL WORKS:
  1. The user asks: "Where is token verification performed?"
  2. Embed the question -> 384-dimensional query vector.
  3. Pre-filter by `repo_id` (so we don't return code from unrelated repositories).
  4. Perform Approximate Nearest Neighbor (ANN) search using cosine distance in ChromaDB.
  5. Return top-k code chunks sorted by relevance, with file paths and line ranges.

INTERVIEW ANGLE:
  "Why is semantic vector search alone sometimes not enough for codebases?"
  Answer:
    Code search often requires exact symbol matching (e.g. `def verify_jwt_token`).
    An embedding model might understand that "token check" is conceptually related,
    but miss the exact function named `verify_jwt_token` if another function has
    more semantically similar prose comments.
    In V4 (Advanced Retrieval), we will implement Hybrid Search:
    combining dense semantic vectors with sparse BM25 keyword matching.
"""

from app.services.vector_store import get_chroma_client


CODE_COLLECTION_NAME = "contexthub_code"

# Shares the same client factory as the document store, so remote Chroma
# (CHROMA_HOST set) is used consistently across both collections.
_client = get_chroma_client()


def get_code_collection():
    """
    Get or create the code vector collection.
    Configured with cosine distance metric for normalized semantic similarity.
    """
    return _client.get_or_create_collection(
        name=CODE_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def add_code_chunks(chunks: list[dict], embeddings: list[list[float]]) -> int:
    """
    Store code chunks and their embeddings into ChromaDB.

    Args:
        chunks: List of chunk dicts from code_parser.py
                Keys: text, file_path, start_line, end_line, language, repo_id, chunk_index
        embeddings: List of float vectors from embedder.py

    Returns:
        Number of chunks stored.
    """
    if not chunks:
        return 0

    collection = get_code_collection()

    ids = []
    documents = []
    metadatas = []

    for chunk in chunks:
        # Create unique, deterministic ID for each chunk
        safe_path = chunk["file_path"].replace("/", "_").replace("\\", "_")
        chunk_id = f"{chunk['repo_id']}_{safe_path}_{chunk['chunk_index']}"
        ids.append(chunk_id)

        documents.append(chunk["text"])

        # ChromaDB metadata must be primitive types: str, int, float, bool
        metadatas.append({
            "repo_id": chunk["repo_id"],
            "file_path": chunk["file_path"],
            "start_line": chunk["start_line"],
            "end_line": chunk["end_line"],
            "language": chunk["language"],
            "chunk_index": chunk["chunk_index"],
        })

    # ChromaDB batch upsert limit: batch into slices of 500 if collection is large
    batch_size = 500
    for i in range(0, len(ids), batch_size):
        collection.upsert(
            ids=ids[i : i + batch_size],
            embeddings=embeddings[i : i + batch_size],
            documents=documents[i : i + batch_size],
            metadatas=metadatas[i : i + batch_size],
        )

    return len(chunks)


def query_code_chunks(
    query_embedding: list[float],
    top_k: int,
    repo_id: str,
    path_filter: str | None = None,
) -> list[dict]:
    """
    Retrieve the top-k most relevant code snippets for a query vector within a repo.

    Args:
        query_embedding: Vector representation of user's code question.
        top_k: Number of snippets to retrieve.
        repo_id: Required repository ID scope.
        path_filter: Optional directory or file prefix to narrow search.

    Returns:
        List of code snippet dictionaries with file paths, line ranges, and scores.
    """
    collection = get_code_collection()

    count = collection.count()
    if count == 0:
        return []

    actual_k = min(top_k, count)

    # Build ChromaDB metadata filter
    where_filter: dict = {"repo_id": repo_id}
    # If path_filter is provided and ChromaDB supports complex where operators:
    # In ChromaDB, $eq is simple; for V3, exact repo_id filter is the primary scope.

    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=actual_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        print(f"[CodeVectorStore] Query error: {e}")
        return []

    if not results or not results["documents"] or not results["documents"][0]:
        return []

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    retrieved: list[dict] = []
    for doc, meta, distance in zip(documents, metadatas, distances):
        # Apply client-side path filter if user requested e.g. path_filter="src/auth"
        if path_filter and not meta["file_path"].startswith(path_filter):
            continue

        retrieved.append({
            "text": doc,
            "file_path": meta["file_path"],
            "start_line": meta["start_line"],
            "end_line": meta["end_line"],
            "language": meta["language"],
            "repo_id": meta["repo_id"],
            "score": round(1 - distance, 4),
        })

    return retrieved


def delete_repo_chunks(repo_id: str) -> None:
    """
    Purge all code chunks for a deleted repository.
    """
    collection = get_code_collection()
    collection.delete(where={"repo_id": repo_id})


def get_code_chunk_count(repo_id: str | None = None) -> int:
    """Return total number of code chunks stored."""
    collection = get_code_collection()
    if repo_id:
        # ChromaDB count doesn't take where filter in all versions; get with where
        res = collection.get(where={"repo_id": repo_id}, include=[])
        return len(res["ids"]) if res and res.get("ids") else 0
    return collection.count()
