"""
rag_pipeline.py — Orchestrates the document RAG pipeline with V4 Advanced Retrieval.

V4 ENHANCEMENTS:
  - Hybrid Retrieval: Dense vector search + BM25 sparse keyword search fused with RRF.
  - Two-Stage Cross-Encoder Reranking for high-precision context selection.
  - Configurable search modes: 'hybrid', 'dense', 'sparse'.
  - Relevance guardrails: Out-of-domain / irrelevant questions are gracefully refused.
"""

import re
import uuid
from pathlib import Path
from typing import Optional

from groq import Groq

from app.config import settings
from app.services.pdf_parser import extract_text_from_pdf, get_pdf_metadata
from app.services.chunker import chunk_pages
from app.services.embedder import embed_texts
from app.services.vector_store import add_chunks, delete_document_chunks
from app.services.document_registry import (
    create_document,
    get_document_by_hash,
    hash_file,
)
from app.services.bm25_indexer import invalidate_bm25_cache
from app.services.hybrid_retriever import retrieve_document_chunks_v4


_groq_client = Groq(api_key=settings.groq_api_key)

# Minimum acceptable rerank score for cross-encoder (logits).
# For ms-marco-MiniLM-L-6-v2, scores below -5.0 generally mean completely irrelevant.
RERANK_THRESHOLD = -5.0
DENSE_THRESHOLD = 0.25


def ingest_pdf(file_path: str | Path, filename: str, owner_id: str) -> dict:
    """
    Ingest a PDF file into the document registry, ChromaDB, and invalidate BM25 cache.

    owner_id (V5): the uploading user. Dedup is scoped per-owner, and the
    registry record is tagged with this owner for multi-tenant access control.
    """
    file_path = Path(file_path)

    print(f"[Ingest] Hashing file '{filename}'...")
    file_hash = hash_file(file_path)

    existing = get_document_by_hash(file_hash, owner_id)
    if existing:
        print(f"[Ingest] Duplicate detected. Reusing existing document ID '{existing.document_id}'.")
        return {
            "document_id": existing.document_id,
            "filename": existing.filename,
            "chunk_count": existing.chunk_count,
            "already_existed": True,
        }

    print(f"[Ingest] Extracting text from '{filename}'...")
    pages = extract_text_from_pdf(file_path)
    print(f"[Ingest] Extracted {len(pages)} pages.")

    pdf_meta = get_pdf_metadata(file_path)

    document_id = str(uuid.uuid4())
    print(f"[Ingest] Chunking pages...")
    chunks = chunk_pages(pages, document_id=document_id)
    print(f"[Ingest] Created {len(chunks)} chunks.")

    print(f"[Ingest] Generating embeddings for {len(chunks)} chunks...")
    chunk_texts = [chunk["text"] for chunk in chunks]
    embeddings = embed_texts(chunk_texts)

    print(f"[Ingest] Storing in ChromaDB...")
    stored_count = add_chunks(chunks, embeddings)

    # Invalidate cached BM25 index so new chunks are reflected
    invalidate_bm25_cache(f"doc:{document_id}")
    invalidate_bm25_cache("doc:all")

    print(f"[Ingest] Saving document record to registry...")
    create_document(
        document_id=document_id,
        owner_id=owner_id,
        filename=filename,
        file_hash=file_hash,
        file_size_bytes=file_path.stat().st_size,
        page_count=pdf_meta["page_count"],
        chunk_count=stored_count,
        title=pdf_meta.get("title", ""),
        author=pdf_meta.get("author", ""),
    )
    print(f"[Ingest] Ingestion complete for '{filename}'.")

    return {
        "document_id": document_id,
        "filename": filename,
        "chunk_count": stored_count,
        "already_existed": False,
    }


def delete_document_from_stores(document_id: str) -> None:
    """
    Purge document chunks from vector store and clear BM25 cache.
    """
    print(f"[Delete] Removing ChromaDB chunks for document '{document_id}'...")
    delete_document_chunks(document_id)
    invalidate_bm25_cache(f"doc:{document_id}")
    invalidate_bm25_cache("doc:all")
    print(f"[Delete] ChromaDB chunks removed.")


def query_rag(
    question: str,
    top_k: Optional[int] = None,
    document_id: Optional[str] = None,
    search_mode: str = "hybrid",
    enable_rerank: bool = True,
) -> dict:
    """
    Advanced RAG query pipeline using Hybrid Retrieval + Reranking.
    """
    k = top_k or settings.top_k_results

    scope = f"document '{document_id}'" if document_id else "all documents"
    print(f"[Query] Retrieving chunks ({search_mode=}, {enable_rerank=}) for: '{question}' from {scope}...")

    # Stage 1 + Stage 2: Advanced retrieval via hybrid_retriever
    retrieved_chunks = retrieve_document_chunks_v4(
        query=question,
        top_k=k,
        document_id=document_id,
        search_mode=search_mode,
        enable_rerank=enable_rerank,
    )
    print(f"[Query] Retrieved {len(retrieved_chunks)} relevant chunks.")

    if not retrieved_chunks:
        return {
            "answer": "No relevant documents or text were found matching your query.",
            "sources": [],
            "question": question,
        }

    # Relevance Guardrail: Rejection of out-of-domain questions
    top_chunk = retrieved_chunks[0]
    if enable_rerank and "rerank_score" in top_chunk:
        if top_chunk["rerank_score"] < RERANK_THRESHOLD:
            print(f"[Query] Guardrail triggered: Top rerank score {top_chunk['rerank_score']} < {RERANK_THRESHOLD}")
            return {
                "answer": (
                    "I could not find relevant information in the uploaded documents to answer your question. "
                    "Please ensure your question pertains to the indexed documents."
                ),
                "sources": [],
                "question": question,
            }
    elif top_chunk.get("score", 0.0) < DENSE_THRESHOLD and not top_chunk.get("bm25_score"):
        print(f"[Query] Guardrail triggered: Top dense score {top_chunk.get('score')} < {DENSE_THRESHOLD}")
        return {
            "answer": (
                "I could not find relevant information in the uploaded documents to answer your question. "
                "Please ensure your question pertains to the indexed documents."
            ),
            "sources": [],
            "question": question,
        }

    context_block = _build_context_block(retrieved_chunks)
    prompt = _build_user_prompt(question, context_block)

    print(f"[Query] Calling Groq ({settings.groq_model}) with {len(retrieved_chunks)} context chunks...")

    response = _groq_client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": _get_system_prompt()},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=800,
    )

    answer = _sanitize_output(response.choices[0].message.content)

    return {
        "answer": answer,
        "sources": retrieved_chunks,
        "question": question,
    }


def _sanitize_output(text: str) -> str:
    """Strip <think>...</think> blocks and any leaked reasoning from the model output."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL)
    # Remove common leaked reasoning prefixes
    text = re.sub(
        r"^(Here's a thinking|Analyze|Scan Context|Extract|Synthesize|Check|Draft|Final Review).*?\n",
        "",
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(r"✅\s*\n?", "", text)
    return text.strip()


def _get_system_prompt() -> str:
    return """You are ContextHub, a document analysis assistant.

Answer questions using ONLY the provided context. Rules:
1. Start directly with the answer. No preamble, no "Based on the documents...", no meta-commentary.
2. If the context lacks sufficient information, reply: "Insufficient information in the provided documents."
3. Cite sources inline using page numbers (e.g. p.4, pp.12-14).
4. Be factual and concise. No speculation, no filler, no hedging.
5. Format: use bullet points for multiple items, bold key terms, and code blocks for technical content.
6. Never say "I think", "It seems", "Let me explain", or similar conversational padding.
7. Never output internal reasoning, chain-of-thought, analysis, or self-correction.
8. Never output <think> or </think> tags.
9. Return ONLY the final answer intended for the user."""


def _build_context_block(chunks: list[dict]) -> str:
    parts = ["--- Context ---"]
    for chunk in chunks:
        score_info = []
        if "rerank_score" in chunk:
            score_info.append(f"Rerank: {chunk['rerank_score']}")
        elif "rrf_score" in chunk:
            score_info.append(f"RRF: {chunk['rrf_score']}")
        elif "score" in chunk and chunk["score"] > 0:
            score_info.append(f"Sim: {chunk['score']}")

        score_tag = f" | {', '.join(score_info)}" if score_info else ""
        parts.append(
            f"\n[Source: {chunk['source']} | Page {chunk['page_number']}{score_tag}]\n{chunk['text']}"
        )
    parts.append("---------------")
    return "\n".join(parts)


def _build_user_prompt(question: str, context_block: str) -> str:
    return f"""{context_block}

Question: {question}

Provide a direct, concise answer with inline page citations. No introductory phrases."""
