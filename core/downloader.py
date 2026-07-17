"""core/downloader.py — Download Hashcat & JtR from GitHub releases.

Handles:
- GitHub API latest release lookup
- File download with progress reporting
- Archive extraction (.7z via py7zr, .zip via zipfile)
- Post-extraction directory discovery
"""

import json
import logging
import zipfile
from collections.abc import Callable
from pathlib import Path
from urllib.request import urlopen, Request

log = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com/repos/{}/releases/latest"
_HEADERS = {"Accept": "application/vnd.github.v3+json", "User-Agent": "Shatter/1.0"}


def _github_latest_release(repo: str) -> dict:
    """Fetch the latest release metadata from GitHub API."""
    url = _GITHUB_API.format(repo)
    req = Request(url, headers=_HEADERS)
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _find_asset(assets: list[dict], must_contain: list[str], extension: str) -> dict | None:
    """Find a release asset whose name contains all given substrings and ends with extension."""
    for asset in assets:
        name = asset["name"].lower()
        if name.endswith(extension) and all(p in name for p in must_contain):
            return asset
    return None


def _download_file(
    url: str,
    dest: Path,
    on_progress: Callable[[int, int], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> None:
    """Download a file from url to dest, calling on_progress(downloaded, total) periodically."""
    req = Request(url, headers={"User-Agent": "Shatter/1.0"})
    with urlopen(req, timeout=600) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0

        with open(dest, "wb") as f:
            while True:
                if is_cancelled and is_cancelled():
                    f.close()
                    dest.unlink(missing_ok=True)
                    raise InterruptedError("Download cancelled by user.")
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if on_progress:
                    on_progress(downloaded, total)

    log.info("Downloaded %s (%d bytes)", dest.name, downloaded)


def _extract_7z(archive: Path, dest: Path) -> None:
    """Extract a .7z archive using py7zr."""
    try:
        import py7zr
    except ImportError:
        raise ImportError(
            "py7zr is required to extract .7z archives. Run: pip install py7zr"
        )
    with py7zr.SevenZipFile(archive, "r") as z:
        z.extractall(dest)


def download_hashcat(
    dest_dir: Path,
    on_progress: Callable[[int, int], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> Path:
    """Download the latest hashcat release and extract it.

    Args:
        dest_dir: Directory to extract into (e.g. APP_ROOT / "hashcat").
        on_progress: Optional callback(downloaded_bytes, total_bytes).

    Returns:
        Path to the directory containing hashcat.exe.

    Raises:
        FileNotFoundError: If the release asset or exe can't be found.
        ImportError: If py7zr is needed but not installed.
    """
    log.info("Fetching latest hashcat release info...")
    release = _github_latest_release("hashcat/hashcat")

    # Prefer .7z (official format)
    asset = _find_asset(release["assets"], ["hashcat"], ".7z")
    if not asset:
        asset = _find_asset(release["assets"], ["hashcat"], ".zip")
    if not asset:
        raise FileNotFoundError("No hashcat download found in latest GitHub release.")

    url = asset["browser_download_url"]
    filename = asset["name"]
    log.info("Downloading %s from %s", filename, url)

    dest_dir.mkdir(parents=True, exist_ok=True)
    archive_path = dest_dir / filename

    _download_file(url, archive_path, on_progress, is_cancelled)

    # Extract
    log.info("Extracting %s...", filename)
    if filename.endswith(".7z"):
        _extract_7z(archive_path, dest_dir)
    else:
        with zipfile.ZipFile(archive_path, "r") as z:
            z.extractall(dest_dir)

    archive_path.unlink(missing_ok=True)

    # Find hashcat.exe in extracted contents
    for item in sorted(dest_dir.iterdir()):
        if item.is_dir() and "hashcat" in item.name.lower():
            exe = item / "hashcat.exe"
            if exe.is_file():
                log.info("Hashcat installed at %s", item)
                return item

    # Maybe extracted flat (no subdirectory)
    if (dest_dir / "hashcat.exe").is_file():
        return dest_dir

    raise FileNotFoundError("hashcat.exe not found after extraction.")


def download_jtr(
    dest_dir: Path,
    on_progress: Callable[[int, int], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> Path:
    """Download the latest John the Ripper release and extract it.

    Args:
        dest_dir: Directory to extract into (e.g. APP_ROOT / "johntheripper").
        on_progress: Optional callback(downloaded_bytes, total_bytes).

    Returns:
        Path to the JtR "run" directory containing *2john tools.

    Raises:
        FileNotFoundError: If the release asset or run dir can't be found.
    """
    log.info("Fetching latest JtR release info...")
    release = _github_latest_release("openwall/john-packages")

    # Look for Windows 64-bit build
    asset = _find_asset(release["assets"], ["win64"], ".zip")
    if not asset:
        asset = _find_asset(release["assets"], ["win", "64"], ".zip")
    if not asset:
        asset = _find_asset(release["assets"], ["windows"], ".zip")
    if not asset:
        raise FileNotFoundError("No JtR Windows download found in latest GitHub release.")

    url = asset["browser_download_url"]
    filename = asset["name"]
    log.info("Downloading %s from %s", filename, url)

    dest_dir.mkdir(parents=True, exist_ok=True)
    archive_path = dest_dir / filename

    _download_file(url, archive_path, on_progress, is_cancelled)

    log.info("Extracting %s...", filename)
    with zipfile.ZipFile(archive_path, "r") as z:
        z.extractall(dest_dir)

    archive_path.unlink(missing_ok=True)

    # Find the "run" directory containing *2john tools
    markers = ["zip2john.exe", "zip2john", "office2john.py", "rar2john.exe"]
    for run_dir in dest_dir.rglob("run"):
        if run_dir.is_dir() and any((run_dir / m).is_file() for m in markers):
            log.info("JtR run directory found at %s", run_dir)
            return run_dir

    raise FileNotFoundError("JtR run directory not found after extraction.")
