import re
from typing import Optional

from rank_bm25 import BM25Okapi


def tokenize(text: str) -> list[str]:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    cleaned = re.sub(r"[^a-zA-Z0-9]", " ", text.lower())
    tokens = [t for t in cleaned.split() if len(t) >= 2]
    return tokens


class BM25Index:
    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        self.tokenized_corpus = [tokenize(c["text"]) for c in chunks]
        if not self.tokenized_corpus or all(len(doc) == 0 for doc in self.tokenized_corpus):
            self.bm25: Optional[BM25Okapi] = None
        else:
            self.bm25 = BM25Okapi(self.tokenized_corpus)

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        if not self.bm25 or not self.chunks:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)
        scored_chunks = []
        for i, score in enumerate(scores):
            if score > 0.0:
                scored_chunks.append({
                    **self.chunks[i],
                    "bm25_score": float(score),
                })

        scored_chunks.sort(key=lambda x: x["bm25_score"], reverse=True)
        top_results = scored_chunks[:top_k]
        for rank, item in enumerate(top_results, start=1):
            item["sparse_rank"] = rank

        return top_results


_index_cache: dict[str, BM25Index] = {}


def get_or_build_bm25_index(cache_key: str, chunks: list[dict]) -> BM25Index:
    if cache_key not in _index_cache or len(_index_cache[cache_key].chunks) != len(chunks):
        _index_cache[cache_key] = BM25Index(chunks)
    return _index_cache[cache_key]


def invalidate_bm25_cache(cache_key: Optional[str] = None) -> None:
    if cache_key:
        _index_cache.pop(cache_key, None)
    else:
        _index_cache.clear()
