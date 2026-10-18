import socket

from app.config import settings


COLLECTION_NAME = "contexthub_documents"


def _preflight_chroma_connection() -> None:
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


def get_chroma_client():
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    kwargs: dict = {"settings": ChromaSettings(anonymized_telemetry=False)}
    if settings.chroma_host:
        _preflight_chroma_connection()
        kwargs.update(
            host=settings.chroma_host,
            port=settings.chroma_port,
            ssl=settings.chroma_ssl,
        )
        if settings.chroma_api_key:
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
    global _client
    if _client is None:
        _client = get_chroma_client()
    return _client


def get_collection():
    return get_client().get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def add_chunks(chunks: list[dict], embeddings: list[list[float]]) -> int:
    collection = get_collection()
    ids = []
    documents = []
    metadatas = []
    for i, chunk in enumerate(chunks):
        chunk_id = f"{chunk['document_id']}_chunk_{chunk['chunk_index']}"
        ids.append(chunk_id)
        documents.append(chunk["text"])
        metadatas.append({
            "page_number": chunk["page_number"],
            "source": chunk["source"],
            "document_id": chunk["document_id"],
            "chunk_index": chunk["chunk_index"],
        })

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )
    return len(chunks)


def query_chunks(
    query_embedding: list[float],
    top_k: int,
    document_id: str | None = None,
) -> list[dict]:
    collection = get_collection()
    count = collection.count()
    if count == 0:
        return []

    actual_top_k = min(top_k, count)
    query_kwargs: dict = dict(
        query_embeddings=[query_embedding],
        n_results=actual_top_k,
        include=["documents", "metadatas", "distances"],
    )
    if document_id:
        query_kwargs["where"] = {"document_id": document_id}

    results = collection.query(**query_kwargs)
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
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
    return get_collection().count()


def delete_document_chunks(document_id: str) -> None:
    collection = get_collection()
    collection.delete(where={"document_id": document_id})
