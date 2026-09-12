"""
pdf_parser.py — Extract text from PDFs, page by page, with metadata.

WHAT THIS MODULE DOES:
  Given a path to a PDF file, it extracts the raw text from each page
  and returns a list of dictionaries, where each dict contains:
    - "text":        the text content of that page
    - "page_number": the 1-indexed page number (humans count from 1, not 0)
    - "source":      the filename (for citation display in the UI)

WHY PAGE-BY-PAGE EXTRACTION?
  We could extract all text as one giant string, but then we'd lose the
  page number information forever. By extracting page-by-page, we can
  attach page_number as metadata to every chunk. When ChromaDB retrieves
  a chunk, we know exactly which page it came from → "See page 4".

WHY PyMuPDF (imported as fitz)?
  - It's a Python binding for MuPDF, a high-performance C PDF engine.
  - Much faster than pypdf (pure Python) and more layout-accurate.
  - Handles complex PDFs better (columns, embedded fonts, etc.).
  - The name 'fitz' is historical — MuPDF's creator has a related name.
  
  Alternatives:
  - pypdf: simpler, pure Python, but slower and less accurate
  - pdfplumber: great for tables, built on pypdf, slower
  - Unstructured: best for complex layouts (tables, headers, images)
                  → we'll use this in V2 for smarter document parsing

WHAT COULD GO WRONG:
  - Scanned PDFs: PyMuPDF extracts text from the PDF's text layer.
    A scanned PDF is just an image — no text layer → extraction returns empty strings.
    Fix: OCR (e.g. pytesseract, Google Document AI). This is V2 scope.
  - Password-protected PDFs: fitz can open them if you provide the password.
    V1: we just raise a clear error.
  - Corrupted PDFs: fitz will raise an exception → we catch and re-raise.

Interview angle:
  "How would you handle scanned PDFs in your RAG pipeline?"
  Answer: Detect empty text extraction, fall back to an OCR step using
  pytesseract or a managed service like AWS Textract or Google Document AI.
  The parsed text then flows through the same chunking/embedding pipeline.
"""

from pathlib import Path


# NOTE: pymupdf (fitz) is imported LAZILY inside each function below, not at
# module import — importing this module runs during boot, and PyMuPDF's native
# libraries inflate the 512MB budget unnecessarily.


def extract_text_from_pdf(file_path: str | Path) -> list[dict]:
    """
    Extract text from a PDF file, page by page.

    Args:
        file_path: path to the PDF file on disk.

    Returns:
        A list of page dictionaries, e.g.:
        [
            {"text": "Annual Leave Policy...", "page_number": 1, "source": "policy.pdf"},
            {"text": "Employees are entitled to...", "page_number": 2, "source": "policy.pdf"},
            ...
        ]
        Pages with no extractable text (e.g. blank pages) are skipped.

    Raises:
        FileNotFoundError: if the path doesn't exist.
        ValueError:        if the PDF has no extractable text (likely scanned).
        RuntimeError:      if fitz fails to open the file (corrupted/password-protected).
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    import pymupdf as fitz

    # fitz.open() loads the PDF into memory.
    # We use a context manager (with) to ensure the file handle is closed
    # even if an exception occurs — good practice for any I/O resource.
    try:
        doc = fitz.open(str(file_path))
    except Exception as e:
        raise RuntimeError(f"Failed to open PDF '{file_path.name}': {e}") from e

    pages: list[dict] = []

    with doc:
        # doc is iterable — each item is a fitz.Page object
        for page_index, page in enumerate(doc):
            # page.get_text() extracts all text from the page's text layer.
            # "text" mode: plain text, preserving newlines between blocks.
            # Other modes: "html", "json", "dict" (more structure, more complex).
            raw_text = page.get_text("text")

            # strip() removes leading/trailing whitespace.
            # If a page is blank or purely an image, raw_text will be empty → skip it.
            text = raw_text.strip()
            if not text:
                continue  # skip blank/image-only pages

            pages.append({
                "text": text,
                "page_number": page_index + 1,  # convert 0-indexed to 1-indexed
                "source": file_path.name,        # just the filename, not the full path
            })

    if not pages:
        raise ValueError(
            f"No extractable text found in '{file_path.name}'. "
            "This PDF may be a scanned image. OCR support is coming in V2."
        )

    return pages


def get_pdf_metadata(file_path: str | Path) -> dict:
    """
    Extract basic metadata from a PDF (title, author, page count).
    
    Useful for V2 document management — display metadata in the UI
    without having to re-read the whole file.
    """
    file_path = Path(file_path)
    import pymupdf as fitz

    doc = fitz.open(str(file_path))

    with doc:
        metadata = doc.metadata  # dict with keys: title, author, subject, creator, etc.
        return {
            "page_count": doc.page_count,
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
        }
