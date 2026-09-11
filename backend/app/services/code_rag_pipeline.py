"""
code_rag_pipeline.py — End-to-end orchestration for codebase ingestion and code Q&A with V4 Advanced Retrieval.

V4 ENHANCEMENTS:
  - Hybrid Code Retrieval: Dense vector search + BM25 keyword search fused via RRF.
  - Cross-Encoder Reranker for high-precision code snippet scoring.
  - Relevance guardrails: Out-of-domain / irrelevant questions gracefully refused.
"""

import re
import shutil
import uuid
from pathlib import Path
from typing import Optional

from app.config import settings
from app.services.llm import complete_chat
from app.services.embedder import embed_texts
from app.services.git_service import (
    clone_repository,
    extract_zip_repository,
    scan_repository_files,
)
from app.services.code_parser import (
    chunk_source_file,
    determine_primary_language,
)
from app.services.code_vector_store import (
    add_code_chunks,
    delete_repo_chunks,
)
from app.services.document_registry import (
    create_repository,
    get_repository_by_id,
    delete_repository,
)
from app.services.bm25_indexer import invalidate_bm25_cache
from app.services.hybrid_retriever import retrieve_code_chunks_v4


RERANK_THRESHOLD = -5.0
DENSE_THRESHOLD = 0.25


def ingest_git_repository(git_url: str, branch: Optional[str] = None, owner_id: str = "") -> dict:
    repo_id = str(uuid.uuid4())
    repo_dest = Path(settings.repo_dir) / repo_id

    print(f"[CodeRAG] Cloning repository '{git_url}' into {repo_dest}...")
    repo_name, commit_hash = clone_repository(git_url, repo_dest, branch=branch)
    print(f"[CodeRAG] Cloned '{repo_name}' (commit: {commit_hash or 'latest'}).")

    return _process_and_index_scanned_repo(
        repo_id=repo_id,
        repo_name=repo_name,
        repo_dest=repo_dest,
        clone_url=git_url,
        commit_hash=commit_hash,
        owner_id=owner_id,
    )


def ingest_zip_repository(zip_path: Path, original_filename: str, owner_id: str = "") -> dict:
    repo_id = str(uuid.uuid4())
    repo_dest = Path(settings.repo_dir) / repo_id

    print(f"[CodeRAG] Extracting archive '{original_filename}' into {repo_dest}...")
    repo_name = extract_zip_repository(zip_path, repo_dest)

    return _process_and_index_scanned_repo(
        repo_id=repo_id,
        repo_name=repo_name,
        repo_dest=repo_dest,
        clone_url=f"upload://{original_filename}",
        commit_hash=None,
        owner_id=owner_id,
    )


def _process_and_index_scanned_repo(
    repo_id: str,
    repo_name: str,
    repo_dest: Path,
    clone_url: str,
    commit_hash: Optional[str],
    owner_id: str = "",
) -> dict:
    scanned_files = scan_repository_files(repo_dest)
    print(f"[CodeRAG] Discovered {len(scanned_files)} valid source code files.")

    if not scanned_files:
        shutil.rmtree(repo_dest, ignore_errors=True)
        raise ValueError("No supported source code files found in the repository.")

    primary_lang = determine_primary_language(scanned_files)

    all_chunks: list[dict] = []
    for f in scanned_files:
        file_chunks = chunk_source_file(
            file_path_rel=f["file_path"],
            file_full_path=f["full_path"],
            repo_id=repo_id,
        )
        all_chunks.extend(file_chunks)

    print(f"[CodeRAG] Created {len(all_chunks)} syntax-aware code chunks across {len(scanned_files)} files.")

    if not all_chunks:
        shutil.rmtree(repo_dest, ignore_errors=True)
        raise ValueError("No readable code chunks could be extracted from repository files.")

    print(f"[CodeRAG] Generating embeddings for {len(all_chunks)} chunks...")
    chunk_texts = [c["text"] for c in all_chunks]
    
    batch_size = 256
    embeddings: list[list[float]] = []
    for i in range(0, len(chunk_texts), batch_size):
        batch = chunk_texts[i : i + batch_size]
        embeddings.extend(embed_texts(batch))

    print(f"[CodeRAG] Indexing chunks in ChromaDB (collection: contexthub_code)...")
    stored_count = add_code_chunks(all_chunks, embeddings)

    # Invalidate BM25 cache for this repository
    invalidate_bm25_cache(f"repo:{repo_id}")

    repo_record = create_repository(
        repo_id=repo_id,
        owner_id=owner_id,
        name=repo_name,
        clone_url=clone_url,
        commit_hash=commit_hash,
        file_count=len(scanned_files),
        chunk_count=stored_count,
        primary_language=primary_lang,
    )

    print(f"[CodeRAG] Ingestion successfully completed for repo '{repo_name}' ({repo_id}).")

    return {
        "repo_id": repo_id,
        "name": repo_name,
        "clone_url": clone_url,
        "commit_hash": commit_hash,
        "file_count": len(scanned_files),
        "chunk_count": stored_count,
        "primary_language": primary_lang,
        "created_at": repo_record.created_at,
    }


def delete_repository_pipeline(repo_id: str, owner_id: str = "") -> None:
    repo = get_repository_by_id(repo_id, owner_id)
    if not repo:
        raise ValueError(f"Repository with ID '{repo_id}' not found.")

    print(f"[CodeRAG] Deleting vector chunks for repo {repo_id}...")
    delete_repo_chunks(repo_id)
    invalidate_bm25_cache(f"repo:{repo_id}")

    print(f"[CodeRAG] Deleting database entry for repo {repo_id}...")
    delete_repository(repo_id, owner_id)

    repo_path = Path(settings.repo_dir) / repo_id
    if repo_path.exists():
        print(f"[CodeRAG] Removing repository directory {repo_path}...")
        shutil.rmtree(repo_path, ignore_errors=True)


def query_codebase(
    question: str,
    repo_id: str,
    path_filter: Optional[str] = None,
    top_k: Optional[int] = None,
    search_mode: str = "hybrid",
    enable_rerank: bool = True,
    owner_id: str = "",
) -> dict:
    repo = get_repository_by_id(repo_id, owner_id)
    if not repo:
        raise ValueError(f"Repository with ID '{repo_id}' does not exist.")

    k = top_k or 5

    print(f"[CodeQuery] Retrieving code ({search_mode=}, {enable_rerank=}) for: '{question}' in repo '{repo.name}'...")

    retrieved_chunks = retrieve_code_chunks_v4(
        query=question,
        repo_id=repo_id,
        top_k=k,
        path_filter=path_filter,
        search_mode=search_mode,
        enable_rerank=enable_rerank,
    )
    print(f"[CodeQuery] Retrieved {len(retrieved_chunks)} code chunks.")

    if not retrieved_chunks:
        return {
            "answer": f"No code snippets were found matching your query in repository '{repo.name}'.",
            "sources": [],
            "question": question,
            "repo_id": repo_id,
        }

    # Relevance Guardrail: Rejection of out-of-domain questions
    top_chunk = retrieved_chunks[0]
    if enable_rerank and "rerank_score" in top_chunk:
        if top_chunk["rerank_score"] < RERANK_THRESHOLD:
            print(f"[CodeQuery] Guardrail triggered: Top rerank score {top_chunk['rerank_score']} < {RERANK_THRESHOLD}")
            return {
                "answer": (
                    f"I could not find relevant code in repository '{repo.name}' to answer your question. "
                    "Please ensure your question is related to the codebase."
                ),
                "sources": [],
                "question": question,
                "repo_id": repo_id,
            }

    context_block = _build_code_context_block(retrieved_chunks)
    prompt = _build_code_prompt(question, repo.name, context_block)

    print(f"[CodeQuery] Querying Groq ({settings.groq_model}) with {len(retrieved_chunks)} code snippets...")

    answer = _sanitize_output(
        complete_chat(
            system=_get_code_system_prompt(),
            user=prompt,
            temperature=0.1,
        )
    )

    return {
        "answer": answer,
        "sources": retrieved_chunks,
        "question": question,
        "repo_id": repo_id,
        "context": context_block,
    }


def _sanitize_output(text: str) -> str:
    """Strip leaked reasoning / thinking blocks from the model output."""
    if not text or not text.strip():
        return text

    # Qwen3-style tag pair: a "thinking" marker line, the reasoning body, then a
    # closing "answer" marker line. Everything up to the closing marker is
    # chain-of-thought and must not be surfaced to the user.
    if re.search(r"^\s*[\[\]`'\"<>]?\s*thinking\b", text, flags=re.IGNORECASE | re.MULTILINE):
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if re.search(r"^\s*[\[\]`'\"<>]?\s*answer\b", line, flags=re.IGNORECASE):
                text = "\n".join(lines[i + 1:])
                break

    # HTML-style wrapped reasoning
    text = re.sub(r"<thinking>.*?</thinking>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<reasoning>.*?</reasoning>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    # OpenAI-style "  thinking\n...\n  response" blocks
    text = re.sub(r"\s{2,}thinking\b.*?\s{2,}response\b", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(
        r"^(Here's a thinking|Analyze|Scan Context|Extract|Synthesize|Check|Draft|Final Review).*?\n",
        "",
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(r"✅\s*\n?", "", text)
    return text.strip()


def _get_code_system_prompt() -> str:
    return """You are ContextHub Code Intelligence, a code analysis assistant.

Answer using ONLY the provided code snippets. Rules:
1. Start directly with the answer. No preamble, no "Let me walk through...", no meta-commentary.
2. Cite code references as `file_path#Lstart-Lend` (e.g. `src/auth/jwt.py#L42-L78`).
3. For definitions: state exact file path and function/class signature.
4. For workflows: trace step-by-step through files with inline citations.
5. Use code blocks for any code examples. Use bullet points for lists.
6. If snippets are insufficient, state what is known and what is missing.
7. Never hallucinate methods, endpoints, or variables not in the context.
8. Never say "I think", "It seems", "Looking at the code", or similar conversational padding.
7. Never output internal reasoning, chain-of-thought, analysis, or self-correction.
8. Never output <think> or </think> tags.
9. Return ONLY the final answer intended for the user."""


def _build_code_context_block(chunks: list[dict]) -> str:
    parts = ["--- Repository Code Context ---"]
    for c in chunks:
        score_info = []
        if "rerank_score" in c:
            score_info.append(f"Rerank: {c['rerank_score']}")
        elif "rrf_score" in c:
            score_info.append(f"RRF: {c['rrf_score']}")
        elif "score" in c and c["score"] > 0:
            score_info.append(f"Sim: {c['score']}")

        score_tag = f" | {', '.join(score_info)}" if score_info else ""
        parts.append(
            f"\n[File: {c['file_path']} | Lines: {c['start_line']}-{c['end_line']} | Language: {c['language']}{score_tag}]\n"
            f"```{c['language'].lower()}\n{c['text']}\n```"
        )
    parts.append("\n------------------------------")
    return "\n".join(parts)


def _build_code_prompt(question: str, repo_name: str, context_block: str) -> str:
    return f"""Repository: {repo_name}

{context_block}

Question: {question}

Provide a direct answer with file path and line number citations. No introductory phrases."""
