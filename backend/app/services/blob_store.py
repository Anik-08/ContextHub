import logging
from pathlib import Path

logger = logging.getLogger("contexthub")


BLOB_ACCESS = "private"


def download_blob_to(blob_url: str, local_path: Path) -> None:
    import urllib.parse
    if not blob_url or not blob_url.startswith(("https://", "http://")):
        raise RuntimeError(f"Invalid blob URL: {blob_url!r}")

    try:
        from vercel.blob import download_file
        download_file(blob_url, str(local_path), access=BLOB_ACCESS)
    except Exception as e:
        raise RuntimeError(f"Failed to download file from Vercel Blob: {e}") from e

    if not Path(local_path).exists():
        raise RuntimeError(f"Blob download produced no file for {urllib.parse.urlparse(blob_url).path}")


def delete_blob(blob_url: str) -> None:
    try:
        from vercel.blob import delete
        delete([blob_url])
        logger.info("Deleted blob %s", blob_url)
    except Exception as e:
        logger.warning("Could not delete blob %s: %s", blob_url, e)
