"""
git_service.py — Ingestion, cloning, extracting, and scanning of code repositories.

WHAT WE ARE BUILDING:
  This service is responsible for getting repository source code onto the local
  filesystem and filtering out irrelevant files:
    1. Shallow clone via Git CLI (`git clone --depth 1`).
    2. ZIP extraction for manually uploaded repositories.
    3. Intelligent file scanning that filters out noise (.git, node_modules, binaries, locks).

WHY SHALLOW CLONE (--depth 1)?
  In production, popular open-source repositories can have gigabytes of Git commit history.
  A standard `git clone` downloads every commit, branch, and diff since the repository's inception.
  A shallow clone (`git clone --depth 1`) only downloads the latest commit snapshot.
  It is 10x-100x faster, uses minimal bandwidth, and saves disk space.

WHY INTELLIGENT FILE FILTERING IS CRITICAL:
  A typical modern web project (e.g. Next.js or Python backend) has thousands of files
  that are NOT human-authored source code:
    - `node_modules/` or `vendor/` (third-party dependencies)
    - `.git/` (git internal database)
    - `package-lock.json` or `uv.lock` (massive generated dependency trees)
    - Minified bundles or build output (`dist/`, `.next/`, `build/`)
    - Binary files (images, audio, compiled binaries)
  If these files enter the vector database:
    - Embedding cost & time skyrockets.
    - Retrieval quality drops because queries match random lockfile hashes or library internals.
    - Garbage in -> Garbage out.

INTERVIEW ANGLE:
  "How would you handle repository ingestion at scale for thousands of users?"
  Answer:
    1. Worker queues: Ingesting a repository is I/O and compute-heavy. It should run
       asynchronously in a background worker (Celery, temporal, or BullMQ), not block
       the HTTP request thread.
    2. Ephemeral sandboxes: Clone into temporary scratch storage or ephemeral volumes.
    3. Rate limits & authentication: Use GitHub App tokens or OAuth for private repos,
       and respect GitHub API rate limits.
    4. Size and file caps: Enforce strict file count and file size limits to prevent DoS.
"""

import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Optional

from app.config import settings


# Common directories that should never be indexed
IGNORED_DIRECTORIES = {
    ".git",
    ".github",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    "out",
    ".next",
    ".nuxt",
    ".turbo",
    "coverage",
    ".idea",
    ".vscode",
    "vendor",
    "target",
    "bin",
    "obj",
}

# Binary and non-code file extensions to ignore
IGNORED_EXTENSIONS = {
    # Images & Media
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".mp4", ".mov", ".mp3",
    # Documents & Archives
    ".pdf", ".zip", ".tar", ".gz", ".7z", ".rar",
    # Binaries & Executables
    ".exe", ".dll", ".so", ".dylib", ".bin", ".iso", ".class", ".pyc", ".pyo", ".wasm",
    # Fonts
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    # Large generated data / locks
    ".lock", ".map", ".min.js", ".min.css",
}

# Source code extensions supported for code intelligence
SUPPORTED_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java",
    ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp",
    ".cs", ".rb", ".php", ".swift", ".kt", ".scala",
    ".sql", ".html", ".css", ".scss",
    ".json", ".yaml", ".yml", ".toml", ".md", ".sh",
}

# Max allowed individual file size (250 KB) to prevent indexing minified files or big datasets
MAX_FILE_SIZE_BYTES = 250 * 1024


def clone_repository(git_url: str, target_dir: Path, branch: Optional[str] = None) -> tuple[str, str]:
    """
    Shallow-clone a Git repository into target_dir.

    Args:
        git_url: HTTPS clone URL.
        target_dir: Local destination directory.
        branch: Optional specific branch or tag to clone.

    Returns:
        tuple (repo_name, commit_hash)

    Raises:
        RuntimeError: If git clone fails.
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    # Derive human-friendly repository name from URL (e.g. 'https://github.com/fastapi/fastapi.git' -> 'fastapi')
    clean_url = git_url.rstrip("/")
    if clean_url.endswith(".git"):
        clean_url = clean_url[:-4]
    repo_name = clean_url.split("/")[-1] or "repository"

    cmd = ["git", "clone", "--depth", "1"]
    if branch:
        cmd.extend(["--branch", branch])
    cmd.extend([git_url, str(target_dir)])

    # Execute git clone via subprocess
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Clean up failed clone folder
        shutil.rmtree(target_dir, ignore_errors=True)
        raise RuntimeError(f"Git clone failed: {result.stderr.strip() or result.stdout.strip()}")

    # Retrieve latest commit hash for tracking
    commit_hash = get_latest_commit_hash(target_dir)

    return repo_name, commit_hash


def extract_zip_repository(zip_path: Path, target_dir: Path) -> str:
    """
    Extract a ZIP archive containing a repository.

    Args:
        zip_path: Path to .zip file.
        target_dir: Local destination directory.

    Returns:
        repo_name: Clean name of the extracted folder.
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        # Security: Prevent Zip Slip vulnerability (directory traversal in zip entries)
        for member in zf.namelist():
            # Resolve destination path
            resolved_path = (target_dir / member).resolve()
            if not str(resolved_path).startswith(str(target_dir.resolve())):
                raise ValueError(f"Malicious zip entry detected: {member}")
        
        zf.extractall(target_dir)

    # Check if archive extracted into a single root folder (common in GitHub downloads: 'repo-main/')
    extracted_items = [p for p in target_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]
    if len(extracted_items) == 1 and not any(p.is_file() for p in target_dir.iterdir()):
        # Repos packaged like `repo-main/...`
        repo_name = extracted_items[0].name
    else:
        repo_name = zip_path.stem

    return repo_name


def get_latest_commit_hash(repo_dir: Path) -> Optional[str]:
    """Get the HEAD commit hash of a git repository."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return None


def scan_repository_files(repo_dir: Path) -> list[dict]:
    """
    Recursively scan repo_dir and collect valid source code files.

    Returns:
        list of dicts:
        [
            {
                "file_path": relative_path_str (e.g. 'app/main.py'),
                "full_path": absolute Path,
                "extension": '.py',
                "size_bytes": 1024,
            },
            ...
        ]
    """
    scanned_files: list[dict] = []

    for root, dirs, files in os.walk(repo_dir):
        # Prune ignored directories in-place so os.walk does not traverse into them
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRECTORIES and not d.startswith(".")]

        for filename in files:
            # Skip hidden files
            if filename.startswith("."):
                continue

            file_ext = Path(filename).suffix.lower()
            
            # Skip ignored extensions
            if file_ext in IGNORED_EXTENSIONS:
                continue

            # Special cases: Dockerfile or Makefile with no extension
            if filename.lower() in {"dockerfile", "makefile", "caddyfile"}:
                file_ext = ".txt"
            elif file_ext not in SUPPORTED_EXTENSIONS:
                continue

            full_path = Path(root) / filename
            try:
                size_bytes = full_path.stat().st_size
            except OSError:
                continue

            # Skip oversized files
            if size_bytes > MAX_FILE_SIZE_BYTES or size_bytes == 0:
                continue

            rel_path = full_path.relative_to(repo_dir).as_posix()

            scanned_files.append({
                "file_path": rel_path,
                "full_path": full_path,
                "extension": file_ext,
                "size_bytes": size_bytes,
            })

    return scanned_files
