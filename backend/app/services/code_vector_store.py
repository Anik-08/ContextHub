from app.services.vector_store import get_client


CODE_COLLECTION_NAME = "contexthub_code"


def get_code_collection():
    return get_client().get_or_create_collection(
        name=CODE_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def add_code_chunks(chunks: list[dict], embeddings: list[list[float]]) -> int:
    if not chunks:
        return 0

    collection = get_code_collection()
    ids = []
    documents = []
    metadatas = []
    for chunk in chunks:
        safe_path = chunk["file_path"].replace("/", "_").replace("\\", "_")
        chunk_id = f"{chunk['repo_id']}_{safe_path}_{chunk['chunk_index']}"
        ids.append(chunk_id)
        documents.append(chunk["text"])
        metadatas.append({
            "repo_id": chunk["repo_id"],
            "file_path": chunk["file_path"],
            "start_line": chunk["start_line"],
            "end_line": chunk["end_line"],
            "language": chunk["language"],
            "chunk_index": chunk["chunk_index"],
        })

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
    collection = get_code_collection()
    count = collection.count()
    if count == 0:
        return []

    actual_k = min(top_k, count)
    where_filter: dict = {"repo_id": repo_id}
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
    collection = get_code_collection()
    collection.delete(where={"repo_id": repo_id})


def get_code_chunk_count(repo_id: str | None = None) -> int:
    collection = get_code_collection()
    if repo_id:
        res = collection.get(where={"repo_id": repo_id}, include=[])
        return len(res["ids"]) if res and res.get("ids") else 0
    return collection.count()
