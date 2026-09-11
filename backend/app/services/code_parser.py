"""
code_parser.py — Language-aware parsing and chunking of source code files.

WHAT WE ARE BUILDING:
  A syntax-aware code chunker that splits source files along logical programming
  boundaries (functions, classes, interfaces, declarations) rather than arbitrary
  character counts. For every generated chunk, it calculates the exact 1-indexed
  `start_line` and `end_line` numbers in the source file.

WHY LANGUAGE-AWARE CHUNKING MATTERS:
  In document RAG, sentences and paragraphs are natural units of meaning.
  In code, the natural units are:
    - Classes
    - Functions / Methods
    - Structs / Interfaces
    - Import / Export blocks
  If a naive character chunker cuts through the middle of a function:
    - The first chunk gets `def authenticate_user(username, password):` with no body.
    - The second chunk gets `if verify_hash(...) return True` with no function signature.
    - Embeddings for both chunks are crippled: neither knows what arguments were passed
      nor what the function was named.

HOW RECURSIVECHARACTERTEXTSPLITTER.FROM_LANGUAGE WORKS:
  LangChain defines hierarchical separators tailored to each programming language:
    - Python:     ["\nclass ", "\ndef ", "\n\tdef ", "\n\n", "\n", " ", ""]
    - JavaScript: ["\nfunction ", "\nconst ", "\nlet ", "\nclass ", "\nexport ", "\n\n", "\n", " "]
    - Go:         ["\nfunc ", "\ntype ", "\nconst ", "\nvar ", "\n\n", "\n", " "]
    - Rust:       ["\nfn ", "\nstruct ", "\nenum ", "\nimpl ", "\ntrait ", "\n\n", "\n", " "]
  It attempts to split on major definition keywords first. Only if a single function
  or class exceeds `chunk_size` does it descend into paragraph or line breaks.

HOW LINE NUMBER TRACKING WORKS:
  To allow developers to click directly to `#L45-L90` in GitHub or an IDE, we track
  where each chunk appears in the original raw file text.
  By counting newlines (`\n`) preceding the chunk's start index, we compute:
    - `start_line = text[:offset].count('\\n') + 1`
    - `end_line = start_line + chunk.count('\\n')`

INTERVIEW ANGLE:
  "What is the difference between AST-based chunking and regex/separator chunking?"
  Answer:
    - AST (Abstract Syntax Tree) chunking parses source into a formal syntax tree
      (e.g. via Python `ast` or `tree-sitter`). It guarantees 100% syntactic validity
      and captures exact symbol names and docstrings, but requires language-specific
      parsers and grammar binaries for every language.
    - Separator/Regex chunking uses language-specific keywords as hierarchy tiers.
      It is fast, fault-tolerant (works even on invalid or uncompilable code),
      and easily supports 20+ languages without native C dependencies.
"""

from collections import Counter
from pathlib import Path
from typing import Optional

from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

from app.config import settings


# Mapping of file extensions to LangChain Language enums
EXTENSION_TO_LANGUAGE: dict[str, Language] = {
    ".py": Language.PYTHON,
    ".js": Language.JS,
    ".jsx": Language.JS,
    ".ts": Language.TS,
    ".tsx": Language.TS,
    ".go": Language.GO,
    ".rs": Language.RUST,
    ".java": Language.JAVA,
    ".cpp": Language.CPP,
    ".cc": Language.CPP,
    ".cxx": Language.CPP,
    ".c": Language.C,
    ".h": Language.C,
    ".hpp": Language.CPP,
    ".cs": Language.CSHARP,
    ".rb": Language.RUBY,
    ".php": Language.PHP,
    ".swift": Language.SWIFT,
    ".kt": Language.KOTLIN,
    ".scala": Language.SCALA,
    ".html": Language.HTML,
    ".md": Language.MARKDOWN,
}

# Human-readable language name mapping
EXTENSION_TO_NAME: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript (React)",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (React)",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".cpp": "C++",
    ".c": "C",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".sql": "SQL",
    ".html": "HTML",
    ".css": "CSS",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".md": "Markdown",
    ".sh": "Shell",
}


def get_language_from_extension(ext: str) -> Optional[Language]:
    """Return LangChain Language enum if supported."""
    return EXTENSION_TO_LANGUAGE.get(ext.lower())


def get_human_language_name(ext: str) -> str:
    """Return clean language name (e.g. 'Python', 'TypeScript')."""
    return EXTENSION_TO_NAME.get(ext.lower(), "Generic Code")


def determine_primary_language(file_list: list[dict]) -> str:
    """
    Find the dominant programming language in the repository by line or file count.
    """
    extensions = [f["extension"] for f in file_list if f["extension"] in EXTENSION_TO_NAME]
    if not extensions:
        return "Unknown"
    
    most_common_ext, _ = Counter(extensions).most_common(1)[0]
    return EXTENSION_TO_NAME.get(most_common_ext, "Unknown")


def chunk_source_file(
    file_path_rel: str,
    file_full_path: Path,
    repo_id: str,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> list[dict]:
    """
    Read and chunk a source code file using syntax-aware splitting.

    Args:
        file_path_rel: Relative path in repo (e.g. 'src/auth/jwt.py').
        file_full_path: Absolute path to read content.
        repo_id: Owning repository ID.
        chunk_size: Maximum characters per chunk (default from config).
        chunk_overlap: Overlap between consecutive chunks.

    Returns:
        list of chunk dictionaries with line range metadata.
    """
    size = chunk_size or settings.code_chunk_size
    overlap = chunk_overlap or settings.code_chunk_overlap

    ext = file_full_path.suffix.lower()
    lang_enum = get_language_from_extension(ext)
    lang_name = get_human_language_name(ext)

    try:
        # Read file with UTF-8 encoding; replace non-decodable characters cleanly
        content = file_full_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"[CodeParser] Error reading {file_path_rel}: {e}")
        return []

    if not content.strip():
        return []

    # Choose appropriate splitter: language-aware if available, otherwise generic recursive
    if lang_enum:
        splitter = RecursiveCharacterTextSplitter.from_language(
            language=lang_enum,
            chunk_size=size,
            chunk_overlap=overlap,
            add_start_index=True,
        )
    else:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=size,
            chunk_overlap=overlap,
            add_start_index=True,
        )

    # create_documents returns list of Document objects with metadata["start_index"]
    docs = splitter.create_documents([content])

    chunks: list[dict] = []

    for i, doc in enumerate(docs):
        chunk_text = doc.page_content.strip()
        if not chunk_text:
            continue

        start_char_idx = doc.metadata.get("start_index", 0)

        # Calculate exact 1-indexed line numbers
        # Count number of newlines from start of file up to start_char_idx
        start_line = content[:start_char_idx].count("\n") + 1
        end_line = start_line + chunk_text.count("\n")

        chunks.append({
            "text": chunk_text,
            "file_path": file_path_rel,
            "start_line": start_line,
            "end_line": end_line,
            "language": lang_name,
            "repo_id": repo_id,
            "chunk_index": i,
        })

    return chunks
