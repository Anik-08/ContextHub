"""
bm25_indexer.py — In-memory Okapi BM25 sparse keyword retrieval index.

WHAT WE ARE BUILDING:
  A sparse lexical search index based on Okapi BM25. It works alongside
  ChromaDB's dense vector index to provide Hybrid Search (keyword + semantic).

WHY WE NEED BM25 (THE LEXICAL GAP IN VECTOR SEARCH):
  Vector embeddings (like all-MiniLM-L6-v2) are great at capturing general semantics:
    - "vacation rules" matches "annual leave policy"
    - "how to log in" matches "user authentication"
  However, vector embeddings struggle with:
    - Exact symbol names: `HTTP_415_UNSUPPORTED_MEDIA_TYPE`
    - Function/Class identifiers: `process_stripe_webhook`
    - Error codes: `ERR_CONNECTION_REFUSED` or `422`
    - Specific numbers, SKUs, or acronyms
  Vector models compress these exact character sequences into dense semantic space,
  often losing exact token matches.
  BM25 is an exact token matching algorithm: if the chunk contains the exact word
  "HTTP_415_UNSUPPORTED_MEDIA_TYPE", BM25 assigns it a massive score.

HOW BM25 WORKS (OKAPI BM25 FORMULA):
  For a query Q containing terms q_1, ..., q_n and a document D:
  
    Score(D, Q) = sum_{i=1}^n IDF(q_i) * [ f(q_i, D) * (k1 + 1) ] / [ f(q_i, D) + k1 * (1 - b + b * (|D| / avgdl)) ]

  Key mechanics:
  1. IDF (Inverse Document Frequency):
     Rare words across the corpus (like "OAuth2") are worth more than common words (like "the").
  2. TF Saturation (k1 parameter, usually 1.5):
     Mentioning a word 20 times does NOT make a passage 20x more relevant than mentioning it twice.
     The curve plateaus, preventing keyword stuffing.
  3. Length Normalization (b parameter, usually 0.75):
     Longer chunks are penalized proportionally so long files don't naturally score higher
     simply because they contain more total words.

CODE-AWARE TOKENIZATION:
  Standard tokenizers split only on spaces. In software engineering:
    - `verify_user_token` (snake_case)
    - `parseDocumentMetadata` (camelCase)
    - `HTTP_415_ERROR` (screaming snake)
  Our tokenizer splits on underscores, camelCase boundaries, and non-alphanumeric characters
  so that searching for "verify" or "token" matches `verify_user_token`.

INTERVIEW ANGLE:
  "What is the difference between Sparse and Dense retrieval?"
  Answer:
    - Sparse retrieval (BM25, TF-IDF, SPLADE): High-dimensional vectors where each
      dimension corresponds to a dictionary term. Most entries are 0. Matches exact
      keywords with zero semantic understanding of synonyms.
    - Dense retrieval (bi-encoders, sentence-transformers): Low-dimensional continuous
      vectors (e.g. 384 or 1536 floats). Every dimension is dense. Matches semantic concepts
      and synonyms, but can miss exact keyword matches.
    - Hybrid retrieval fuses both to get the recall of dense + the precision of sparse.
"""

import re
from typing import Optional

from rank_bm25 import BM25Okapi


def tokenize(text: str) -> list[str]:
    """
    Code and prose-aware tokenization:
      1. Converts to lowercase.
      2. Splits camelCase (e.g. 'getUserById' -> 'get', 'user', 'by', 'id').
      3. Splits on non-alphanumeric characters (underscores, dots, dashes, slashes).
      4. Filters out empty and single-character tokens.
    """
    # Split camelCase: insert space before capital letters preceded by lowercase
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    # Replace non-alphanumeric characters with spaces
    cleaned = re.sub(r"[^a-zA-Z0-9]", " ", text.lower())
    # Extract tokens with length >= 2
    tokens = [t for t in cleaned.split() if len(t) >= 2]
    return tokens


class BM25Index:
    """
    In-memory BM25 index over a collection of text chunks.
    """

    def __init__(self, chunks: list[dict]):
        """
        Build an Okapi BM25 index from a list of chunk dictionaries.
        Each chunk must have a 'text' key.
        """
        self.chunks = chunks
        self.tokenized_corpus = [tokenize(c["text"]) for c in chunks]
        
        # If corpus is empty or has only empty docs, create fallback
        if not self.tokenized_corpus or all(len(doc) == 0 for doc in self.tokenized_corpus):
            self.bm25: Optional[BM25Okapi] = None
        else:
            self.bm25 = BM25Okapi(self.tokenized_corpus)

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """
        Score and rank chunks against query using BM25.

        Returns:
            list of chunk dicts sorted by BM25 score descending, with:
            - chunk data (text, metadata)
            - 'bm25_score': raw float score
            - 'sparse_rank': 1-indexed rank
        """
        if not self.bm25 or not self.chunks:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        # Get scores for all documents in the corpus
        scores = self.bm25.get_scores(query_tokens)

        # Pair each chunk with its score
        scored_chunks = []
        for i, score in enumerate(scores):
            if score > 0.0:  # Only include chunks that matched at least one term
                scored_chunks.append({
                    **self.chunks[i],
                    "bm25_score": float(score),
                })

        # Sort descending by BM25 score
        scored_chunks.sort(key=lambda x: x["bm25_score"], reverse=True)

        top_results = scored_chunks[:top_k]
        for rank, item in enumerate(top_results, start=1):
            item["sparse_rank"] = rank

        return top_results


# ---------------------------------------------------------------------------
# Global In-Memory Index Cache
# ---------------------------------------------------------------------------
# Key: 'doc:{document_id}' or 'repo:{repo_id}' or 'all_docs'
_index_cache: dict[str, BM25Index] = {}


def get_or_build_bm25_index(cache_key: str, chunks: list[dict]) -> BM25Index:
    """
    Get cached BM25 index or construct and cache a new one.
    """
    if cache_key not in _index_cache or len(_index_cache[cache_key].chunks) != len(chunks):
        _index_cache[cache_key] = BM25Index(chunks)
    return _index_cache[cache_key]


def invalidate_bm25_cache(cache_key: Optional[str] = None) -> None:
    """Clear BM25 cache when documents or repos are added or deleted."""
    if cache_key:
        _index_cache.pop(cache_key, None)
    else:
        _index_cache.clear()
