from collections import Counter
from pathlib import Path
from typing import Optional

from app.config import settings
from app.services.recursive_text_splitter import (
    DEFAULT_SEPARATORS,
    LANGUAGE_SEPARATORS,
    split_recursive_text_with_indices,
)


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


def get_separators_for_extension(ext: str) -> tuple[list[str], bool]:
    seps = LANGUAGE_SEPARATORS.get(ext.lower())
    if seps is None:
        return DEFAULT_SEPARATORS, False
    return seps, True


def get_human_language_name(ext: str) -> str:
    return EXTENSION_TO_NAME.get(ext.lower(), "Generic Code")


def determine_primary_language(file_list: list[dict]) -> str:
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
    size = chunk_size or settings.code_chunk_size
    overlap = chunk_overlap or settings.code_chunk_overlap
    ext = file_full_path.suffix.lower()
    lang_name = get_human_language_name(ext)
    try:
        content = file_full_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"[CodeParser] Error reading {file_path_rel}: {e}")
        return []

    if not content.strip():
        return []

    separators, is_regex = get_separators_for_extension(ext)
    split_results = split_recursive_text_with_indices(
        content,
        separators=separators,
        chunk_size=size,
        chunk_overlap=overlap,
        is_separator_regex=is_regex,
    )
    chunks: list[dict] = []
    for i, (chunk_text, start_char_idx) in enumerate(split_results):
        chunk_text = chunk_text.strip()
        if not chunk_text:
            continue

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
