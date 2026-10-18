from app.config import settings
from app.services.recursive_text_splitter import (
    DEFAULT_SEPARATORS,
    split_recursive_text,
)


def chunk_pages(pages: list[dict], document_id: str) -> list[dict]:
    all_chunks: list[dict] = []
    chunk_index = 0
    for page in pages:
        page_chunks = split_recursive_text(
            page["text"],
            separators=DEFAULT_SEPARATORS,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        for chunk_text in page_chunks:
            chunk_text = chunk_text.strip()
            if not chunk_text:
                continue

            all_chunks.append({
                "text": chunk_text,
                "page_number": page["page_number"],
                "source": page["source"],
                "document_id": document_id,
                "chunk_index": chunk_index,
            })
            chunk_index += 1

    return all_chunks
