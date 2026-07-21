import logging
import subprocess
import sys
from pathlib import Path

from core.cap_parser import cap_to_hc22000_string

def _get_python_interpreter() -> str:
    import shutil
    is_frozen = getattr(sys, 'frozen', False)
    if not is_frozen:
        return sys.executable
    for name in ("python3", "python", "python3.exe", "python.exe"):
        path = shutil.which(name)
        if path:
            return path
    raise FileNotFoundError("Python interpreter not found.")

log = logging.getLogger(__name__)

# Mapping: file extension -> (extractor tool, extra args)
HASH_EXTRACTORS: dict[str, tuple[str, list[str]]] = {
    ".zip":  ("zip2john.exe",     []),
    ".rar":  ("rar2john.exe",     []),
    ".7z":   ("7z2john.pl",   []),
    ".pdf":  ("pdf2john.pl",  []),
    ".docx": ("office2john.py",[]),
    ".xlsx": ("office2john.py",[]),
    ".pptx": ("office2john.py",[]),
    ".doc":  ("office2john.py",[]),
    ".xls":  ("office2john.py",[]),
    ".kdbx": ("keepass2john.exe",  []),
    ".ssh":  ("ssh2john.py",  []),
    ".gpg":  ("gpg2john.exe",     []),
    ".pfx":  ("pfx2john.py",  []),
}

# Extensions handled natively by cap_parser (not via *2john tools)
CAP_EXTENSIONS = {".cap", ".pcap", ".pcapng"}

import os

def _calculate_timeout(filepath: str, base: int = 30, per_mb: int = 10, max_timeout: int = 300) -> int:
    try:
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
    except OSError:
        return base
    return min(base + int(size_mb * per_mb), max_timeout)

from core.result import ParseResult

def extract_hash_from_file(filepath: str, jtr_dir: Path) -> ParseResult:
    """
    Try to extract a hash from an encrypted file.
    Returns: ParseResult
    """
    ext = Path(filepath).suffix.lower()

    if ext in CAP_EXTENSIONS:
        res = cap_to_hc22000_string(filepath)
        if not res.ok:
            return ParseResult(error=res.error)
        return ParseResult(data=res.data, engine="hashcat")

    extractor = HASH_EXTRACTORS.get(ext)

    if not extractor:
        supported = ', '.join(sorted(set(HASH_EXTRACTORS) | CAP_EXTENSIONS))
        return ParseResult(error=f"No extractor for '{ext}' files. Supported: {supported}")

    tool, extra = extractor
    tool_path = jtr_dir / tool

    if not tool_path.exists():
        return ParseResult(error=f"'{tool}' not found in {jtr_dir}.")

    cmd: list[str] = [str(tool_path)] + extra + [filepath]

    if tool.endswith(".py"):
        try:
            python = _get_python_interpreter()
            cmd = [python] + cmd
        except FileNotFoundError as e:
            return ParseResult(error=str(e))
    elif tool.endswith(".pl"):
        import shutil
        perl = shutil.which("perl")
        if not perl:
            return ParseResult(error="Perl interpreter not found.")
        cmd = [perl] + cmd

    log.info("Running: %s", ' '.join(cmd))
    timeout = _calculate_timeout(filepath)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        output = result.stdout.strip()
        if not output and result.stderr.strip():
            return ParseResult(error=f"{tool} error: {result.stderr.strip()}")
        if not output:
            return ParseResult(error=f"{tool} returned no output.")

        lines = output.splitlines()
        raw_hash_line = ""
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.lower().startswith(("warning:", "file ", "usage:", "note:")):
                continue

            if ':$' in stripped or stripped.startswith('$'):
                raw_hash_line = stripped
                break

        if not raw_hash_line:
            return ParseResult(error=f"No valid hash pattern found in {tool} output.")

        return ParseResult(data=raw_hash_line, engine="jtr")

    except FileNotFoundError:
        return ParseResult(error=f"'{tool}' not found. Install John the Ripper and ensure it's in PATH.")
    except subprocess.TimeoutExpired:
        return ParseResult(error=f"'{tool}' timed out.")
    except Exception as e:
        return ParseResult(error=f"Extraction failed: {e}")
