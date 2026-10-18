from app.config import settings


_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        print(f"Loading embedding model: {settings.embedding_model}...")
        _embedder = DefaultEmbeddingFunction()
        print("Embedding model loaded.")
    return _embedder


def _normalize(raw):
    import numpy as np
    return np.asarray(raw).tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    return _normalize(_get_embedder().embed_query(texts))


def embed_query(query: str) -> list[float]:
    return _normalize(_get_embedder().embed_query([query]))[0]


def get_embedding_dimension() -> int:
    return len(embed_query("test"))


def get_embedding_model():
    return _get_embedder()
