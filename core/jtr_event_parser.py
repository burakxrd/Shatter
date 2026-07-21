import re

_RE_JTR_CRACKED = re.compile(r'^(?:[^:]+:\s*)?(.*?)\s+\((.*)\)$')
_RE_JTR_STATUS = re.compile(r'^(\d+)g\s+(\d+:\d+:\d+:\d+)\s+DONE\s+(.*)')
_RE_JTR_PROGRESS = re.compile(r'(\d+(?:\.\d+)?)%\s+\(ETA:\s*([^)]+)\)')

def parse_jtr_line(line: str) -> dict | None:
    """Parse a raw John the Ripper output line into a structured event dict."""
    s = line.rstrip('\n').rstrip('\r').strip()
    if not s:
        return None

    if s.startswith("─") or s.startswith("===="):
        return {"type": "separator"}
    if s.startswith("[!"):
        return {"type": "error", "data": {"message": s[3:].strip()}}
    if s.startswith("[+]"):
        return {"type": "success", "data": {"message": s[3:].strip()}}
    if s.startswith("[*]"):
        return {"type": "info", "data": {"message": s[3:].strip()}}

    # E.g. "password123      (admin)"
    if " (" in s and s.endswith(")"):
        m = _RE_JTR_CRACKED.match(s)
        if m:
            pwd = m.group(1).strip()
            return {"type": "hash_cracked", "data": {"hash": "Session Result", "password": pwd}}

    m = _RE_JTR_STATUS.match(s)
    if m:
        return {"type": "status", "data": {"status": "Completed"}}

    m = _RE_JTR_PROGRESS.match(s)
    if m:
        # e.g., "15.5% (ETA: 12:34:56)"
        percent = m.group(1)
        eta = m.group(2)
        return {"type": "progress", "data": {"current": percent, "total": "100", "percent": percent}}

    if s.lower().startswith("warning:"):
        return None
    if s.startswith("Using default input encoding"):
        return None
    if s.startswith("Loaded ") and "password" in s:
        return {"type": "info", "data": {"message": s}}

    return {"type": "log", "data": {"message": s}}
