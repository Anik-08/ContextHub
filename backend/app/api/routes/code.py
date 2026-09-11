"""
code.py — API routes for Codebase Intelligence (Git ingestion, Zip upload, Listing, Querying).

ENDPOINTS:
  - POST   /api/code/ingest-git  → Shallow clone a public Git repo URL and index source code
  - POST   /api/code/upload-zip  → Upload and index a repository .zip file
  - GET    /api/code/repos       → List all indexed repositories
  - DELETE /api/code/repos/{id}  → Delete repository across SQLite, ChromaDB, and disk
  - POST   /api/code/query       → Query code architecture & implementation with line citations

WHY DEDICATED CODE ENDPOINTS?
  Code search requires different input parameters (e.g. Git URLs, branch names, path filters)
  and produces different responses (exact line numbers, function signatures, file paths)
  than document RAG. Separating `/api/code` from `/api/documents` ensures a clean,
  extensible REST API interface.
"""

import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status

from app.models.schemas import (
    RepoIngestGitRequest,
    RepoResponse,
    RepoListResponse,
    DeleteRepoResponse,
    CodeQueryRequest,
    CodeQueryResponse,
    CodeSourceChunk,
)
from app.models.db_models import User
from app.services.auth_deps import get_current_user
from app.services.code_rag_pipeline import (
    ingest_git_repository,
    ingest_zip_repository,
    delete_repository_pipeline,
    query_codebase,
)
from app.services.document_registry import (
    get_all_repositories,
    get_repository_by_id,
)


router = APIRouter(prefix="/api/code", tags=["Code Intelligence"])


@router.post(
    "/ingest-git",
    response_model=RepoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Clone and index a Git repository from URL",
    description=(
        "Clones a public Git repository (shallow clone with --depth 1), scans source files, "
        "chunks them along language syntax boundaries, generates embeddings, and indexes them."
    ),
)
async def ingest_git_repo_endpoint(
    request: RepoIngestGitRequest,
    user: User = Depends(get_current_user),
) -> RepoResponse:
    try:
        result = ingest_git_repository(
            git_url=request.git_url,
            branch=request.branch,
            owner_id=user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clone and index repository: {str(e)}",
        )

    return RepoResponse(
        repo_id=result["repo_id"],
        name=result["name"],
        clone_url=result["clone_url"],
        commit_hash=result["commit_hash"],
        file_count=result["file_count"],
        chunk_count=result["chunk_count"],
        primary_language=result["primary_language"],
        created_at=result["created_at"],
        message=f"Successfully indexed '{result['name']}' ({result['file_count']} files, {result['chunk_count']} code chunks).",
    )


@router.post(
    "/upload-zip",
    response_model=RepoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and index a repository .zip archive",
    description="Extracts a .zip archive of a codebase, filters out non-source files, and indexes code chunks.",
)
async def upload_zip_repo_endpoint(
    file: UploadFile = File(..., description="Repository .zip file"),
    user: User = Depends(get_current_user),
) -> RepoResponse:
    if not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only .zip repository archives are supported.",
        )

    # Stream upload to temporary file
    with NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        result = ingest_zip_repository(
            zip_path=tmp_path,
            original_filename=file.filename,
            owner_id=user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract and index repository: {str(e)}",
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    return RepoResponse(
        repo_id=result["repo_id"],
        name=result["name"],
        clone_url=result["clone_url"],
        commit_hash=result["commit_hash"],
        file_count=result["file_count"],
        chunk_count=result["chunk_count"],
        primary_language=result["primary_language"],
        created_at=result["created_at"],
        message=f"Successfully indexed archive '{file.filename}' ({result['chunk_count']} chunks).",
    )


@router.get(
    "/repos",
    response_model=RepoListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all indexed code repositories",
)
async def list_repositories(user: User = Depends(get_current_user)) -> RepoListResponse:
    repos = get_all_repositories(user.user_id)
    records = [
        RepoResponse(
            repo_id=r.repo_id,
            name=r.name,
            clone_url=r.clone_url,
            commit_hash=r.commit_hash,
            file_count=r.file_count,
            chunk_count=r.chunk_count,
            primary_language=r.primary_language,
            created_at=r.created_at,
        )
        for r in repos
    ]
    return RepoListResponse(repos=records, total=len(records))


@router.delete(
    "/repos/{repo_id}",
    response_model=DeleteRepoResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete an indexed repository",
    description="Removes repository records from SQLite, vector chunks from ChromaDB, and local repository files.",
)
async def delete_repository_endpoint(
    repo_id: str,
    user: User = Depends(get_current_user),
) -> DeleteRepoResponse:
    repo = get_repository_by_id(repo_id, user.user_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID '{repo_id}' not found.",
        )

    try:
        delete_repository_pipeline(repo_id, owner_id=user.user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete repository: {str(e)}",
        )

    return DeleteRepoResponse(
        repo_id=repo_id,
        message=f"Repository '{repo.name}' and all associated code vectors deleted successfully.",
    )


@router.post(
    "/query",
    response_model=CodeQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a question about an indexed codebase",
    description=(
        "Retrieves relevant code snippets from ChromaDB and uses Groq to generate "
        "a grounded architectural or implementation explanation with exact file and line citations."
    ),
)
async def query_code_endpoint(
    request: CodeQueryRequest,
    user: User = Depends(get_current_user),
) -> CodeQueryResponse:
    try:
        result = query_codebase(
            question=request.question,
            repo_id=request.repo_id,
            path_filter=request.path_filter,
            top_k=request.top_k,
            search_mode=request.search_mode,
            enable_rerank=request.enable_rerank,
            owner_id=user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code query failed: {str(e)}",
        )

    sources = [
        CodeSourceChunk(
            content=c["text"],
            file_path=c["file_path"],
            start_line=c["start_line"],
            end_line=c["end_line"],
            language=c["language"],
            repo_id=c["repo_id"],
            score=c.get("score", 0.0),
            bm25_score=c.get("bm25_score"),
            rrf_score=c.get("rrf_score"),
            rerank_score=c.get("rerank_score"),
        )
        for c in result["sources"]
    ]

    return CodeQueryResponse(
        answer=result["answer"],
        sources=sources,
        question=result["question"],
        repo_id=result["repo_id"],
    )
