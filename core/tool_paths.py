"""core.tool_paths — Hashcat & JtR path discovery, validation, and persistence.

First-run flow:
  1. Load saved paths from config
  2. Validate them (exe exists + runs)
  3. If invalid → auto-search common locations + PATH
  4. If still not found → user picks manually via setup dialog
  5. Save valid paths → never ask again
"""

import logging
import shutil
import subprocess
import sys
from pathlib import Path

from core import APP_ROOT

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────
#  Common search locations (Windows-focused)
# ──────────────────────────────────────────────

_HASHCAT_SEARCH = [
    APP_ROOT / "hashcat",
    Path("C:/hashcat"),
    Path("C:/Tools/hashcat"),
    Path("C:/Program Files/hashcat"),
    Path("C:/Program Files (x86)/hashcat"),
]

_JTR_SEARCH = [
    APP_ROOT / "johntheripper" / "run",
    APP_ROOT / "john" / "run",
    Path("C:/john/run"),
    Path("C:/Tools/john/run"),
    Path("C:/Program Files/john/run"),
    Path("C:/Program Files (x86)/john/run"),
]

if sys.platform == "win32":
    _home = Path.home()
    _HASHCAT_SEARCH += [
        _home / "hashcat",
        _home / "Desktop" / "hashcat",
        _home / "Downloads" / "hashcat",
        _home / "Tools" / "hashcat",
    ]
    _JTR_SEARCH += [
        _home / "john" / "run",
        _home / "Tools" / "john" / "run",
    ]


# ──────────────────────────────────────────────
#  Validation
# ──────────────────────────────────────────────

def _find_hashcat_exe(directory: Path) -> Path | None:
    for name in ("hashcat.exe", "hashcat"):
        exe = directory / name
        if exe.is_file():
            return exe
    return None


def validate_hashcat(directory: str | Path) -> Path | None:
    d = Path(directory)
    if not d.is_dir():
        return None
    exe = _find_hashcat_exe(d)
    if not exe:
        return None
    try:
        r = subprocess.run(
            [str(exe), "--version"],
            capture_output=True, text=True, timeout=10, cwd=str(d),
            # CREATE_NO_WINDOW is safe here: this is --version only, no CTRL_BREAK needed.
            # (stream_process uses SW_HIDE instead for actual cracking sessions.)
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if r.returncode == 0 and r.stdout.strip():
            log.info("Hashcat validated: %s (%s)", exe, r.stdout.strip())
            return exe
    except Exception as e:
        log.debug("Hashcat validation failed at %s: %s", exe, e)
    return None


def validate_jtr(run_dir: str | Path) -> Path | None:
    d = Path(run_dir)
    if not d.is_dir():
        return None
    markers = ["zip2john.exe", "zip2john", "office2john.py", "rar2john.exe"]
    if any((d / m).is_file() for m in markers):
        log.info("JtR validated: %s", d)
        return d
    return None


# ──────────────────────────────────────────────
#  Auto-discovery
# ──────────────────────────────────────────────

def find_hashcat() -> Path | None:
    for search_dir in _HASHCAT_SEARCH:
        exe = validate_hashcat(search_dir)
        if exe:
            return exe
    which = shutil.which("hashcat") or shutil.which("hashcat.exe")
    if which:
        exe_path = Path(which)
        if validate_hashcat(exe_path.parent):
            return exe_path
    log.warning("Hashcat not found in any common location.")
    return None


def find_jtr() -> Path | None:
    for search_dir in _JTR_SEARCH:
        result = validate_jtr(search_dir)
        if result:
            return result
    which = shutil.which("john") or shutil.which("john.exe")
    if which:
        run_dir = Path(which).parent
        if validate_jtr(run_dir):
            return run_dir
    log.warning("John the Ripper not found in any common location.")
    return None


# ──────────────────────────────────────────────
#  Path State (module-level, set once at startup)
# ──────────────────────────────────────────────

hashcat_exe: Path | None = None
hashcat_dir: Path | None = None
jtr_dir: Path | None = None


def configure(config: dict) -> dict[str, str]:
    global hashcat_exe, hashcat_dir, jtr_dir
    result = {"hashcat_dir": "", "jtr_dir": ""}

    saved_hc = config.get("hashcat_dir", "")
    if saved_hc:
        exe = validate_hashcat(saved_hc)
        if exe:
            hashcat_exe = exe
            hashcat_dir = exe.parent
            result["hashcat_dir"] = str(hashcat_dir)

    if not hashcat_exe:
        exe = find_hashcat()
        if exe:
            hashcat_exe = exe
            hashcat_dir = exe.parent
            result["hashcat_dir"] = str(hashcat_dir)

    saved_jtr = config.get("jtr_dir", "")
    if saved_jtr:
        d = validate_jtr(saved_jtr)
        if d:
            jtr_dir = d
            result["jtr_dir"] = str(jtr_dir)

    if not jtr_dir:
        d = find_jtr()
        if d:
            jtr_dir = d
            result["jtr_dir"] = str(jtr_dir)

    log.info("Tool paths — hashcat: %s, jtr: %s", hashcat_exe, jtr_dir)
    return result


def set_hashcat_dir(path: str) -> bool:
    global hashcat_exe, hashcat_dir
    exe = validate_hashcat(path)
    if exe:
        hashcat_exe = exe
        hashcat_dir = exe.parent
        return True
    return False


def set_jtr_dir(path: str) -> bool:
    global jtr_dir
    d = validate_jtr(path)
    if d:
        jtr_dir = d
        return True
    return False
