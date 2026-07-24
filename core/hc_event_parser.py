import re

_NOISE_PREFIXES = (
    "Minimum password", "Maximum password",
    "Minimum salt length", "Maximum salt length",
    "Optimizers applied", "Watchdog:", "Hashes:", "Bitmaps:", "Rules:",
    "CUDA API", "OpenCL API",
    "Kernel.Feature", "Guess.Queue", "Guess.Base", "Rejected",
    "Restore.Point", "Restore.Sub", "Candidate.Engine",
    "Candidates.#", "Hardware.Mon",
    "ATTENTION!", "Pure kernels", "If you want to switch",
    "See the above message",
    "Started:", "Stopped:",
    "Dictionary cache", "Initializing",
    "Benchmarking uses",
)
_NOISE_CONTAINS = ("Please be patient", "nvmlDeviceGetFanSpeed", "[s]tatus [p]ause")

_RE_VERSION   = re.compile(r'^hashcat \(v([\d.]+)\) starting')
_RE_DEVICE    = re.compile(r'^\*\s*Device\s*#(\d+):\s*(.+?)(?:,\s*(\d+)/(\d+)\s*MB(?:\s*\([^)]*\))?)?(?:,\s*(\d+)MCU)?$')
_RE_FILENAME  = re.compile(r'^\*\s*Filename\.*:\s*(.+)')
_RE_PASSWORDS = re.compile(r'^\*\s*Passwords\.*:\s*([\d,]+)')
_RE_HASH_MODE = re.compile(r'^Hash[.\s]*Mode\.*:\s*(\d+)\s*\((.+)\)')
_RE_HASHMODE_BENCH = re.compile(r'^Hashmode:\s*(\d+)\s*-\s*(.+)')
_RE_STATUS    = re.compile(r'^Status\.*:\s*(.+)')
_RE_SPEED     = re.compile(r'^Speed\.#(\d+|\*)\.*:\s*(.+?)(?:\s*@|$)')
_RE_RECOVERED = re.compile(r'^Recovered\.*:\s*(\d+)/(\d+)\s*\(([\d.]+)%\)')
_RE_PROGRESS  = re.compile(r'^Progress\.*:\s*([\d,]+)/([\d,]+)\s*\(([\d.]+)%\)')
_RE_ETA       = re.compile(r'^Time\.Estimated\.*:\s*(.+)')
_RE_STARTED   = re.compile(r'^Time\.Started\.*:\s*(.+)')
_RE_STATUS_LINE = re.compile(r'^[\w.*#]+\.+:\s')

def parse_hc_line(line: str) -> dict | None:
    """Parse a raw hashcat output line into a structured event dict."""
    s = line.rstrip('\n').rstrip('\r').strip()
    if not s:
        return None

    if s.startswith("─") or s.startswith("===="):
        return {"type": "separator"}
    if s.startswith("[!"):
        return {"type": "error", "data": {"message": s[3:].strip()}}
    if s.startswith("ERROR:"):
        return {"type": "error", "data": {"message": s[6:].strip()}}
    if s.startswith("[+]"):
        return {"type": "success", "data": {"message": s[3:].strip()}}
    if s.startswith("[*]"):
        return {"type": "info", "data": {"message": s[3:].strip()}}

    if s.startswith("✅"):
        if s.startswith("✅  PASSWORD:") or s.startswith("✅  PASSWORD FOUND:"):
            parts = s.split(":", 1)
            if len(parts) == 2:
                pwd = parts[1].strip()
                return {"type": "hash_cracked", "data": {"hash": "Session Result", "password": pwd}}
        return {"type": "success", "data": {"message": s[1:].strip()}}
    if "❌" in s:
        return {"type": "error", "data": {"message": s.replace("❌", "").strip()}}

    m = _RE_VERSION.match(s)
    if m:
        return {"type": "session_start", "data": {"version": m.group(1)}}

    m = _RE_DEVICE.match(s)
    if m:
        if "skipped" in s.lower():
            return None
        return {"type": "device_info", "data": {
            "id": m.group(1),
            "name": m.group(2).strip().rstrip(','),
            "memory_total": m.group(4) or "",
            "mcu": m.group(5) or "",
        }}

    m = _RE_FILENAME.match(s)
    if m:
        path = m.group(1).strip()
        name = path.replace('\\', '/').rsplit('/', 1)[-1]
        return {"type": "wordlist_file", "data": {"path": path, "name": name}}

    m = _RE_PASSWORDS.match(s)
    if m:
        return {"type": "wordlist_count", "data": {"count": m.group(1).replace(',', '')}}

    if s.startswith("* "):
        return None

    m = _RE_HASH_MODE.match(s) or _RE_HASHMODE_BENCH.match(s)
    if m:
        return {"type": "hash_mode", "data": {"mode": m.group(1), "name": m.group(2).strip()}}

    m = _RE_STATUS.match(s)
    if m:
        st = m.group(1).strip()
        return {"type": "status", "data": {"status": st}}

    m = _RE_SPEED.match(s)
    if m:
        return {"type": "speed", "data": {"device": m.group(1), "speed": m.group(2).strip()}}

    m = _RE_RECOVERED.match(s)
    if m:
        return {"type": "recovered", "data": {"found": m.group(1), "total": m.group(2), "percent": m.group(3)}}

    m = _RE_PROGRESS.match(s)
    if m:
        return {"type": "progress", "data": {"current": m.group(1).replace(',', ''), "total": m.group(2).replace(',', ''), "percent": m.group(3)}}

    m = _RE_ETA.match(s)
    if m:
        return {"type": "eta", "data": {"eta": m.group(1).strip()}}
        
    m = _RE_STARTED.match(s)
    if m:
        return {"type": "started", "data": {"started": m.group(1).strip()}}

    if any(s.startswith(p) for p in _NOISE_PREFIXES):
        return None
    if any(c in s for c in _NOISE_CONTAINS):
        return None

    if _RE_STATUS_LINE.match(s):
        return None

    return {"type": "log", "data": {"message": s}}
