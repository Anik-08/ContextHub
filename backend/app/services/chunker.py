"""
chunker.py — Split extracted PDF pages into smaller, overlapping text chunks.

THE CORE PROBLEM CHUNKING SOLVES:
  LLMs have a context window limit (e.g. 8K, 32K, 128K tokens).
  A 200-page PDF might be ~400K tokens — far too large to send to the LLM directly.
  
  Solution: split the document into small chunks, store all of them in ChromaDB,
  and at query time retrieve only the top-k most relevant chunks.
  Those chunks form the "context" you send to the LLM.

WHY CHUNK SIZE MATTERS:
  - Too large (e.g. 4000 chars): each chunk carries too much irrelevant text.
    The embedding represents the average meaning of all that text → diluted signal.
    Retrieval is less precise.
  - Too small (e.g. 100 chars): a chunk loses surrounding context.
    "20 days" alone means nothing without "annual leave entitlement: 20 days".
  - Sweet spot for prose documents: ~500-1500 characters (~100-250 words).

WHY OVERLAP MATTERS:
  Documents have ideas that span across chunk boundaries.
  Example (chunk_size=50, overlap=20):
    Chunk 1: "Employees are entitled to 20 days of annual"
    Chunk 2: "of annual leave per calendar year. Leave must"
    Chunk 3: "Leave must be applied for two weeks in advance"
  
  Without overlap, the boundary between chunk 1 and 2 would split
  "20 days of annual leave" — losing meaning. Overlap prevents this.

WHY RecursiveCharacterTextSplitter?
  It tries to split on natural boundaries in order of preference:
    1. "\n\n" (paragraph breaks) — most natural
    2. "\n"   (line breaks)
    3. " "    (spaces — word boundaries)
    4. ""     (character level — last resort)
  
  It recurses down the list only if the chunk is still too large after splitting.
  This preserves semantic units (paragraphs > sentences > words) as much as possible.
  
  Alternative splitters:
  - CharacterTextSplitter: splits on a single separator only (less smart)
  - SpacyTextSplitter: uses NLP sentence detection (slower, more accurate)
  - SemanticChunker: uses embeddings to find topic boundaries (expensive, V4)

WHAT METADATA DO WE ATTACH TO EACH CHUNK?
  Every chunk dict carries:
    - text:          the chunk content
    - page_number:   which PDF page it came from (for citations)
    - source:        the filename
    - document_id:   a unique ID for the parent document
    - chunk_index:   position within the document (useful for debugging)

Interview angle:
  "What chunking strategy would you use for technical documentation vs. legal documents?"
  Answer: Technical docs often have clear section headers → use header-aware splitting
  (e.g. Markdown splitter). Legal docs have dense paragraphs → semantic chunking or
  larger chunks with more overlap. The key insight: chunking is domain-specific.
  
  "What is the chunk size / overlap tradeoff?"
  Answer: (see above — you now know this cold)
"""

from app.config import settings


def chunk_pages(pages: list[dict], document_id: str) -> list[dict]:
    """
    Take extracted pages and split them into overlapping chunks.

    Args:
        pages:       output of pdf_parser.extract_text_from_pdf()
                     list of {"text", "page_number", "source"} dicts
        document_id: unique ID for the document these pages belong to.
                     We attach this to every chunk for filtering in V2.

    Returns:
        list of chunk dicts, each containing:
        {
            "text":        str  — the chunk content
            "page_number": int  — source page number
            "source":      str  — filename
            "document_id": str  — parent document ID
            "chunk_index": int  — sequential chunk number (0-indexed)
        }
    
    Data flow:
        pages (list of page dicts)
            → for each page, split text into chunks
            → attach metadata to each chunk
            → return flat list of all chunks across all pages
    """
    # Instantiate the splitter with our config values.
    # We could also pass in chunk_size/chunk_overlap as params for more flexibility.
    # NOTE: imported lazily — `langchain_text_splitters` eagerly imports
    # sentence-transformers/PyTorch at module load, which OOMs 512MB hosts
    # during boot. It is only needed when a document is actually ingested.
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        # length_function: how to measure chunk size.
        # len() counts characters. Alternative: count tokens (more accurate for LLMs).
        # Token counting is slower but prevents accidentally exceeding context windows.
        # V1: character counting is fine. V4: switch to tiktoken-based counting.
        length_function=len,
        # add_start_index: attach the character offset of each chunk in the original text.
        # Useful for advanced highlighting features (V2+). Adds minor overhead.
        add_start_index=True,
    )

    all_chunks: list[dict] = []
    chunk_index = 0

    for page in pages:
        # splitter.split_text() returns a list of strings — the chunks from this page's text.
        # It handles the recursive splitting logic internally.
        page_chunks = splitter.split_text(page["text"])

        for chunk_text in page_chunks:
            # Strip whitespace that can accumulate from splitting
            chunk_text = chunk_text.strip()
            if not chunk_text:
                continue  # skip empty chunks (can happen with lots of whitespace)

            all_chunks.append({
                "text": chunk_text,
                "page_number": page["page_number"],
                "source": page["source"],
                "document_id": document_id,
                "chunk_index": chunk_index,
            })
            chunk_index += 1

    return all_chunks
