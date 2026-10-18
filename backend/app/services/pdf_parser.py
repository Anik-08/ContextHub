from pathlib import Path


def extract_text_from_pdf(file_path: str | Path) -> list[dict]:
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    import pymupdf as fitz
    try:
        doc = fitz.open(str(file_path))
    except Exception as e:
        raise RuntimeError(f"Failed to open PDF '{file_path.name}': {e}") from e

    pages: list[dict] = []
    with doc:
        for page_index, page in enumerate(doc):
            raw_text = page.get_text("text")
            text = raw_text.strip()
            if not text:
                continue

            pages.append({
                "text": text,
                "page_number": page_index + 1,
                "source": file_path.name,
            })

    if not pages:
        raise ValueError(
            f"No extractable text found in '{file_path.name}'. "
            "This PDF may be a scanned image. OCR support is coming in V2."
        )

    return pages


def get_pdf_metadata(file_path: str | Path) -> dict:
    file_path = Path(file_path)
    import pymupdf as fitz
    doc = fitz.open(str(file_path))
    with doc:
        metadata = doc.metadata
        return {
            "page_count": doc.page_count,
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
        }
