import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status

from app.config import settings
from app.models.schemas import (
    BlobIngestRequest,
    DocumentUploadResponse,
    DocumentListResponse,
    DocumentRecord,
    DeleteDocumentResponse,
)
from app.models.db_models import User
from app.services.auth_deps import get_current_user
from app.services.rag_pipeline import ingest_pdf, delete_document_from_stores
from app.services.document_registry import (
    get_all_documents,
    get_document_by_id,
    delete_document,
)
from app.services.blob_store import download_blob_to


router = APIRouter(prefix="/api/documents", tags=["Documents"])

Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

ALLOWED_CONTENT_TYPES = {"application/pdf"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a PDF document",
    description=(
        "Upload a PDF file. Automatically checks for duplicates using SHA-256. "
        "If new, extracts text, chunks it, embeds with sentence-transformers, "
        "stores in ChromaDB, and registers in SQLite."
    ),
)
async def upload_document(
    file: UploadFile = File(..., description="The PDF file to upload and ingest."),
    user: User = Depends(get_current_user),
) -> DocumentUploadResponse:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Only PDF files are supported. Got: {file.content_type}",
        )

    safe_filename = Path(file.filename).name
    file_path = Path(settings.upload_dir) / safe_filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_size = file_path.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        file_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({file_size / 1024 / 1024:.1f} MB) exceeds limit of 50 MB.",
        )

    try:
        result = ingest_pdf(file_path=file_path, filename=safe_filename, owner_id=user.user_id)
    except ValueError as e:
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process document: {str(e)}",
        )

    if result.get("already_existed"):
        message = f"Document '{safe_filename}' was already indexed. Reusing existing document ID {result['document_id']}."
    else:
        message = f"Successfully ingested '{safe_filename}' into {result['chunk_count']} searchable chunks."

    return DocumentUploadResponse(
        document_id=result["document_id"],
        filename=result["filename"],
        chunk_count=result["chunk_count"],
        already_existed=result.get("already_existed", False),
        message=message,
    )


@router.post(
    "/upload-blob",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a PDF uploaded to Vercel Blob",
    description=(
        "Serverless variant of /upload. The browser PUTs the PDF to Vercel Blob "
        "(bypassing the 4.5MB function request-body limit), then posts {blob_url, "
        "filename} here. Downloads the file, then runs the standard ingestion "
        "pipeline (dedup, parse, chunk, embed, index)."
    ),
)
async def upload_document_from_blob(
    request: BlobIngestRequest,
    user: User = Depends(get_current_user),
) -> DocumentUploadResponse:
    safe_filename = Path(request.filename).name
    if not safe_filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are supported.",
        )

    tmp_path = Path(settings.upload_dir) / f"blob-{uuid.uuid4().hex}.pdf"
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        download_blob_to(request.blob_url, tmp_path)
        file_size = tmp_path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size ({file_size / 1024 / 1024:.1f} MB) exceeds limit of 50 MB.",
            )

        result = ingest_pdf(file_path=tmp_path, filename=safe_filename, owner_id=user.user_id)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process document: {str(e)}",
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    if result.get("already_existed"):
        message = f"Document '{safe_filename}' was already indexed. Reusing existing document ID {result['document_id']}."
    else:
        message = f"Successfully ingested '{safe_filename}' into {result['chunk_count']} searchable chunks."

    return DocumentUploadResponse(
        document_id=result["document_id"],
        filename=result["filename"],
        chunk_count=result["chunk_count"],
        already_existed=result.get("already_existed", False),
        message=message,
    )


@router.get(
    "",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all indexed documents",
    description="Returns all registered documents stored in SQLite, ordered by newest first.",
)
async def list_documents(user: User = Depends(get_current_user)) -> DocumentListResponse:
    docs = get_all_documents(user.user_id)
    records = [
        DocumentRecord(
            document_id=d.document_id,
            filename=d.filename,
            file_hash=d.file_hash,
            file_size_bytes=d.file_size_bytes,
            page_count=d.page_count,
            chunk_count=d.chunk_count,
            title=d.title,
            author=d.author,
            uploaded_at=d.uploaded_at,
        )
        for d in docs
    ]
    return DocumentListResponse(documents=records, total=len(records))


@router.delete(
    "/{document_id}",
    response_model=DeleteDocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a document and its embeddings",
    description=(
        "Deletes the document entry from SQLite and purges all associated vector "
        "chunks from ChromaDB."
    ),
)
async def delete_document_endpoint(
    document_id: str,
    user: User = Depends(get_current_user),
) -> DeleteDocumentResponse:
    existing_doc = get_document_by_id(document_id, user.user_id)
    if not existing_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )

    try:
        delete_document_from_stores(document_id)
        delete_document(document_id, user.user_id)
        local_file = Path(settings.upload_dir) / existing_doc.filename
        if local_file.exists():
            local_file.unlink(missing_ok=True)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document '{document_id}': {str(e)}",
        )

    return DeleteDocumentResponse(
        document_id=document_id,
        message=f"Document '{existing_doc.filename}' and its chunks have been permanently deleted.",
    )
