import logging
import subprocess
import sys
from pathlib import Path

from core.cap_parser import cap_to_hc22000_string

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

def extract_hash_from_file(filepath: str, jtr_dir: Path) -> dict:
    """
    Try to extract a hash from an encrypted file.
    Returns: {"hash": extracted_hash, "engine": "jtr" | "hashcat", "error": err_msg}
    """
    ext = Path(filepath).suffix.lower()

    if ext in CAP_EXTENSIONS:
        res = cap_to_hc22000_string(filepath)
        if res.startswith("[!]"):
            return {"hash": "", "engine": "", "error": res}
        return {"hash": res, "engine": "hashcat", "error": None}

    extractor = HASH_EXTRACTORS.get(ext)

    if not extractor:
        supported = ', '.join(sorted(set(HASH_EXTRACTORS) | CAP_EXTENSIONS))
        return {"hash": "", "engine": "", "error": f"[!] No extractor for '{ext}' files. Supported: {supported}"}

    tool, extra = extractor
    tool_path = jtr_dir / tool

    if not tool_path.exists():
        return {"hash": "", "engine": "", "error": f"[!] '{tool}' not found in {jtr_dir}."}

    cmd: list[str] = [str(tool_path)] + extra + [filepath]

    if tool.endswith(".py"):
        cmd = ["python"] + cmd
    elif tool.endswith(".pl"):
        cmd = ["perl"] + cmd

    log.info("Running: %s", ' '.join(cmd))

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        output = result.stdout.strip()
        if not output and result.stderr.strip():
            return {"hash": "", "engine": "", "error": f"[!] {tool} error: {result.stderr.strip()}"}
        if not output:
            return {"hash": "", "engine": "", "error": f"[!] {tool} returned no output."}

        lines = output.splitlines()
        extracted = ""
        for line in lines:
            line = line.strip()
            if not line or line.startswith("Warning:") or line.startswith("File "):
                continue

            if ':$' in line:
                extracted = '$' + line.split(':$', 1)[1]
                break
            elif line.startswith('$'):
                extracted = line
                break

        if not extracted:
            extracted = output

        # For Hashcat compatibility, we used to strip metadata.
        # But for JtR, we want the raw string (usually filename:$hash).
        # We will return the raw string to be used directly by JtR.
        # NTH or detector can still parse the hash type.
        # Actually, to be safe, we return the raw line that contains the hash.
        raw_hash_line = extracted
        for line in lines:
            if ':$' in line or line.startswith('$'):
                raw_hash_line = line
                break

        return {"hash": raw_hash_line.strip(), "engine": "jtr", "error": None}

    except FileNotFoundError:
        return {"hash": "", "engine": "", "error": f"[!] '{tool}' not found. Install John the Ripper and ensure it's in PATH."}
    except subprocess.TimeoutExpired:
        return {"hash": "", "engine": "", "error": f"[!] '{tool}' timed out."}
    except Exception as e:
        return {"hash": "", "engine": "", "error": f"[!] Extraction failed: {e}"}
