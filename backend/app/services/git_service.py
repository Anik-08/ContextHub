import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Optional


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


IGNORED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".mp4", ".mov", ".mp3",
    ".pdf", ".zip", ".tar", ".gz", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".iso", ".class", ".pyc", ".pyo", ".wasm",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".lock", ".map", ".min.js", ".min.css",
}


SUPPORTED_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java",
    ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp",
    ".cs", ".rb", ".php", ".swift", ".kt", ".scala",
    ".sql", ".html", ".css", ".scss",
    ".json", ".yaml", ".yml", ".toml", ".md", ".sh",
}


MAX_FILE_SIZE_BYTES = 250 * 1024


def clone_repository(git_url: str, target_dir: Path, branch: Optional[str] = None) -> tuple[str, str]:
    target_dir.mkdir(parents=True, exist_ok=True)
    clean_url = git_url.rstrip("/")
    if clean_url.endswith(".git"):
        clean_url = clean_url[:-4]
    repo_name = clean_url.split("/")[-1] or "repository"
    cmd = ["git", "clone", "--depth", "1"]
    if branch:
        cmd.extend(["--branch", branch])
    cmd.extend([git_url, str(target_dir)])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        shutil.rmtree(target_dir, ignore_errors=True)
        raise RuntimeError(f"Git clone failed: {result.stderr.strip() or result.stdout.strip()}")

    commit_hash = get_latest_commit_hash(target_dir)
    return repo_name, commit_hash


def extract_zip_repository(zip_path: Path, target_dir: Path) -> str:
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            resolved_path = (target_dir / member).resolve()
            if not str(resolved_path).startswith(str(target_dir.resolve())):
                raise ValueError(f"Malicious zip entry detected: {member}")
        
        zf.extractall(target_dir)

    extracted_items = [p for p in target_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]
    if len(extracted_items) == 1 and not any(p.is_file() for p in target_dir.iterdir()):
        repo_name = extracted_items[0].name
    else:
        repo_name = zip_path.stem

    return repo_name


def get_latest_commit_hash(repo_dir: Path) -> Optional[str]:
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
    scanned_files: list[dict] = []
    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRECTORIES and not d.startswith(".")]
        for filename in files:
            if filename.startswith("."):
                continue

            file_ext = Path(filename).suffix.lower()
            if file_ext in IGNORED_EXTENSIONS:
                continue

            if filename.lower() in {"dockerfile", "makefile", "caddyfile"}:
                file_ext = ".txt"
            elif file_ext not in SUPPORTED_EXTENSIONS:
                continue

            full_path = Path(root) / filename
            try:
                size_bytes = full_path.stat().st_size
            except OSError:
                continue

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
