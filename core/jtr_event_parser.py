import re

_NOISE_PATTERNS = [
    re.compile(r'^Using default input encoding', re.IGNORECASE),
    re.compile(r'^Loaded \d+ password hash', re.IGNORECASE),
    re.compile(r'^Warning:', re.IGNORECASE),
    re.compile(r'^Press .+ to ', re.IGNORECASE),
    re.compile(r'^Proceeding with', re.IGNORECASE),
    re.compile(r'^John the Ripper', re.IGNORECASE), # Fix for banner False Positives
]

_RE_JTR_CRACKED = re.compile(r'^(?:[^:]+:\s*)?(.*?)\s+\(([^)]{1,64})\)$')
_RE_JTR_STATUS = re.compile(r'^(\d+)g\s+(\d+:\d+:\d+:\d+)\s+DONE\s+(.*)')
_RE_JTR_PROGRESS = re.compile(r'(\d+(?:\.\d+)?)%\s+\(ETA:\s*([^)]+)\)')

def parse_jtr_line(line: str) -> dict | None:
    """Parse a raw John the Ripper output line into a structured event dict."""
    s = line.rstrip('\n').rstrip('\r').strip()
    if not s:
        return None

    # NOISE filter
    for pattern in _NOISE_PATTERNS:
        if pattern.search(s):
            if "loaded" in s.lower() and "password" in s.lower():
                return {"type": "info", "data": {"message": s}}
            return None

    if s.startswith("─") or s.startswith("===="):
        return {"type": "separator"}
    if s.startswith("[!"):
        return {"type": "error", "data": {"message": s[3:].strip()}}
    if s.startswith("[+]"):
        return {"type": "success", "data": {"message": s[3:].strip()}}
    if s.startswith("[*]"):
        return {"type": "info", "data": {"message": s[3:].strip()}}

    m = _RE_JTR_STATUS.match(s)
    if m:
        return {"type": "status", "data": {"status": "Completed"}}

    m = _RE_JTR_PROGRESS.search(s)
    if m:
        percent = m.group(1)
        eta = m.group(2)
        return {"type": "progress", "data": {"current": percent, "total": "100", "percent": percent}}

    # E.g. "password123      (admin)"
    if " (" in s and s.endswith(")"):
        m = _RE_JTR_CRACKED.match(s)
        if m:
            pwd = m.group(1).strip()
            # Reject if the 'password' part looks like a JtR status/banner line
            if " DONE " in pwd or pwd.startswith("Warning:") or pwd.startswith("Cost "):
                pass
            elif pwd.lower().startswith("john the ripper") or pwd.lower().startswith("linux") or pwd.lower().startswith("macos"):
                pass # Extra safety net for banners like "John the Ripper 1.9.0-jumbo-1 (Windows)"
            else:
                user_or_hash = m.group(2).strip() if m.lastindex and m.lastindex >= 2 else "N/A"
                return {"type": "hash_cracked", "data": {"hash": user_or_hash, "password": pwd}}

    return {"type": "log", "data": {"message": s}}
