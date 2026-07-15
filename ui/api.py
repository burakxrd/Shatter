"""
api.py — Python-to-JS Bridge for Shatter (pywebview).

All public methods return a standardised response envelope:
    {"success": True,  "data": {...}, "error": None}
    {"success": False, "data": None,  "error": "message"}
This allows the JS frontend to use a single error-handling path.
"""

import json
import logging
import threading

from pathlib import Path
import webview

from core.engine import HashcatEngine
from core.detector import detect_hash_type
from core import TEMP_DIR
import core.tool_paths as tool_paths

log = logging.getLogger(__name__)
CONFIG_FILE = TEMP_DIR / "config.json"


# ──────────────────────────────────────────────
#  Standard Response Helpers
# ──────────────────────────────────────────────

def _ok(data=None) -> dict:
    """Return a successful API response."""
    return {"success": True, "data": data, "error": None}


def _err(message: str) -> dict:
    """Return an error API response."""
    return {"success": False, "data": None, "error": message}


# ──────────────────────────────────────────────
#  Hashcat Output → Structured Event Parser
# ──────────────────────────────────────────────

import re as _re

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

# Compiled regexes for hashcat line parsing
_RE_VERSION   = _re.compile(r'^hashcat \(v([\d.]+)\) starting')
_RE_DEVICE    = _re.compile(r'^\*\s*Device\s*#(\d+):\s*(.+?)(?:,\s*(\d+)/(\d+)\s*MB)?(?:,\s*(\d+)MCU)?$')
_RE_FILENAME  = _re.compile(r'^\*\s*Filename\.*:\s*(.+)')
_RE_PASSWORDS = _re.compile(r'^\*\s*Passwords\.*:\s*([\d,]+)')
_RE_HASH_MODE = _re.compile(r'^Hash[.\s]*Mode\.*:\s*(\d+)\s*\((.+)\)')
_RE_HASHMODE_BENCH = _re.compile(r'^Hashmode:\s*(\d+)\s*-\s*(.+)')
_RE_STATUS    = _re.compile(r'^Status\.*:\s*(.+)')
_RE_SPEED     = _re.compile(r'^Speed\.#(\d+)\.*:\s*(.+?)(?:\s*@|$)')
_RE_RECOVERED = _re.compile(r'^Recovered\.*:\s*(\d+)/(\d+)\s*\(([\d.]+)%\)')
_RE_PROGRESS  = _re.compile(r'^Progress\.*:\s*([\d,]+)/([\d,]+)\s*\(([\d.]+)%\)')
_RE_ETA       = _re.compile(r'^Time\.Estimated\.*:\s*(.+)')
_RE_STARTED   = _re.compile(r'^Time\.Started\.*:\s*(.+)')
_RE_STATUS_LINE = _re.compile(r'^[\w.*#]+\.+:\s')  # generic status line pattern


def _parse_hashcat_line(line: str) -> dict | None:
    """Parse a raw hashcat output line into a structured event dict.

    Returns a dict like {"type": "...", "data": {...}} or None to suppress.
    """
    s = line.rstrip('\n').rstrip('\r').strip()
    if not s:
        return None

    # ── Separator lines ──
    if s.startswith("─") or s.startswith("===="):
        return {"type": "separator"}

    # ── Our custom bracket messages ──
    if s.startswith("[!"):
        return {"type": "error", "data": {"message": s[3:].strip()}}
    if s.startswith("[+]"):
        return {"type": "success", "data": {"message": s[3:].strip()}}
    if s.startswith("[*]"):
        return {"type": "info", "data": {"message": s[3:].strip()}}

    # ── Emoji-prefixed lines from engine ──
    if "✅" in s:
        if "PASSWORD" in s:
            parts = s.split(":", 1)
            if len(parts) == 2:
                pwd = parts[1].strip()
                return {"type": "hash_cracked", "data": {"hash": "Session Result", "password": pwd}}
        # Do not emit a redundant generic success if we just got a password
        return {"type": "success", "data": {"message": s.replace("✅", "").strip()}}
    if "❌" in s:
        return {"type": "error", "data": {"message": s.replace("❌", "").strip()}}

    # ── Hashcat version ──
    m = _RE_VERSION.match(s)
    if m:
        return {"type": "session_start", "data": {"version": m.group(1)}}

    # ── Device info ──
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

    # ── Wordlist filename ──
    m = _RE_FILENAME.match(s)
    if m:
        path = m.group(1).strip()
        name = path.replace('\\', '/').rsplit('/', 1)[-1]
        return {"type": "wordlist_file", "data": {"path": path, "name": name}}

    # ── Password count ──
    m = _RE_PASSWORDS.match(s)
    if m:
        return {"type": "wordlist_count", "data": {"count": m.group(1).replace(',', '')}}

    # ── Other * lines → noise ──
    if s.startswith("* "):
        return None

    # ── Hash.Mode (crack) or Hashmode: (benchmark) ──
    m = _RE_HASH_MODE.match(s) or _RE_HASHMODE_BENCH.match(s)
    if m:
        return {"type": "hash_mode", "data": {"mode": m.group(1), "name": m.group(2).strip()}}

    # ── Status ──
    m = _RE_STATUS.match(s)
    if m:
        return {"type": "status", "data": {"status": m.group(1).strip()}}

    # ── Speed ──
    m = _RE_SPEED.match(s)
    if m:
        return {"type": "speed", "data": {"device": m.group(1), "speed": m.group(2).strip()}}

    # ── Recovered ──
    m = _RE_RECOVERED.match(s)
    if m:
        return {"type": "recovered", "data": {
            "found": m.group(1), "total": m.group(2), "percent": m.group(3),
        }}

    # ── Progress ──
    m = _RE_PROGRESS.match(s)
    if m:
        return {"type": "progress", "data": {
            "current": m.group(1).replace(',', ''),
            "total": m.group(2).replace(',', ''),
            "percent": m.group(3),
        }}

    # ── ETA ──
    m = _RE_ETA.match(s)
    if m:
        raw = m.group(1).strip()
        eta_match = _re.search(r'\((.+)\)', raw)
        eta = eta_match.group(1) if eta_match else raw
        return {"type": "eta", "data": {"eta": eta, "raw": raw}}

    # ── Time started ──
    m = _RE_STARTED.match(s)
    if m:
        return None  # We track start time via UI, no need to duplicate

    # ── Hash target / Session name → noise (shown in dashboard) ──
    if _re.match(r'^Hash\.Target\.*:', s) or _re.match(r'^Session\.*:', s):
        return None

    # ── Known noise ──
    if s.startswith(_NOISE_PREFIXES):
        return None
    for kw in _NOISE_CONTAINS:
        if kw in s:
            return None

    # ── Cracked hash line: HASH:PASSWORD ──
    if ':' in s:
        if not _RE_STATUS_LINE.match(s) and not s.startswith(('hashcat ', 'Host', 'nvml', 'CUDA', 'OpenCL')):
            parts = s.split(':')
            password = parts[-1]
            hash_val = ':'.join(parts[:-1])
            if hash_val and password:
                return {"type": "hash_cracked", "data": {"hash": hash_val, "password": password}}

    # ── Unknown → suppress for clean log ──
    return None


# ──────────────────────────────────────────────
#  API Class
# ──────────────────────────────────────────────

class Api:
    def __init__(self):
        self._window: webview.Window | None = None
        self._engine = HashcatEngine(
            hashcat_exe=tool_paths.hashcat_exe,
            hashcat_dir=tool_paths.hashcat_dir,
            jtr_dir=tool_paths.jtr_dir,
        )

    # ── Internal Helpers ──

    def _sync_engine_paths(self):
        """Keep engine paths in sync with tool_paths module state."""
        self._engine.hashcat_exe = tool_paths.hashcat_exe
        self._engine.hashcat_dir = tool_paths.hashcat_dir
        self._engine.jtr_dir = tool_paths.jtr_dir

    def _on_hashcat_output(self, line: str):
        event = _parse_hashcat_line(line)
        if event and self._window:
            safe = json.dumps(event)
            self._window.evaluate_js(f"onHashcatEvent({safe})")
                
    def _on_crack_done(self):
        if self._window:
            self._window.evaluate_js("onCrackDone()")

    # ── Hash Detection & Extraction ──

    def detect_hash(self, hash_value: str) -> dict:
        from core.detector import extract_m_value
        algo = detect_hash_type(hash_value)
        m_value = extract_m_value(algo) or "0"
        return _ok({"algo": algo, "m_value": m_value})

    def extract_hash(self) -> dict:
        if not self._window:
            return _err("No window")
        result = self._window.create_file_dialog(webview.OPEN_DIALOG)
        if result and len(result) > 0:
            path = result[0]
            self._sync_engine_paths()
            extracted = self._engine.extract_hash_from_file(path)
            if extracted.startswith("[!]"):
                return _err(extracted)
            return _ok({"hash": extracted})
        return _ok({"cancelled": True})

    def load_hash_file(self) -> dict:
        if not self._window:
            return _err("No window")
        result = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=("Text Files (*.txt)", "All Files (*.*)"))
        if result and len(result) > 0:
            return _ok({"path": result[0]})
        return _ok({"cancelled": True})

    def select_wordlist(self) -> dict:
        if not self._window:
            return _err("No window")
        result = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=("Text Files (*.txt)", "All Files (*.*)"))
        if result and len(result) > 0:
            return _ok({"path": result[0]})
        return _ok({"cancelled": True})

    def add_rule(self) -> dict:
        if not self._window:
            return _err("No window")
        result = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=("Rule Files (*.rule)", "All Files (*.*)"))
        if result and len(result) > 0:
            return _ok({"path": result[0]})
        return _ok({"cancelled": True})

    # ── Crack Operations ──

    def start_crack(self, settings: dict) -> dict:
        self._sync_engine_paths()
        if self._engine.is_running:
            return _err("Hashcat is already running.")

        hash_val = settings.get("hash", "")
        m_val = settings.get("m_value", "0")

        # Clear log on start
        if self._window:
            self._window.evaluate_js("clearHashcatOutput()")

        threading.Thread(
            target=self._engine.run_crack,
            args=(hash_val, m_val, settings, self._on_hashcat_output, self._on_crack_done),
            daemon=True
        ).start()

        return _ok({"status": "started"})

    def restore_crack(self, session_name: str) -> dict:
        self._sync_engine_paths()
        if self._engine.is_running:
            return _err("Hashcat is already running.")

        if self._window:
            self._window.evaluate_js("clearHashcatOutput()")

        threading.Thread(
            target=self._engine.run_restore,
            args=(session_name, self._on_hashcat_output, self._on_crack_done),
            daemon=True
        ).start()
        return _ok({"status": "restoring"})

    def stop_crack(self) -> dict:
        self._engine.stop()
        return _ok()

    def pause_crack(self) -> dict:
        """Toggle pause state. Returns paused=True if NOW paused, paused=False if NOW running."""
        if self._engine.is_paused:
            self._engine.resume()
            return _ok({"paused": False})
        else:
            self._engine.pause()
            return _ok({"paused": True})

    def checkpoint_crack(self) -> dict:
        self._engine.checkpoint()
        return _ok()

    def get_devices(self) -> dict:
        self._sync_engine_paths()
        devices = self._engine.get_devices()
        return _ok([{"id": d[0], "name": d[1]} for d in devices])

    def run_benchmark(self, device_id: str) -> dict:
        self._sync_engine_paths()
        if self._engine.is_running:
            return _err("Wait for active run to finish.")

        if self._window:
            self._window.evaluate_js("clearHashcatOutput()")

        threading.Thread(
            target=self._engine.run_benchmark,
            args=(device_id, self._on_hashcat_output, self._on_crack_done),
            daemon=True
        ).start()
        return _ok({"status": "started"})

    # ── File / Folder Dialogs ──

    def browse_folder(self) -> dict:
        if not self._window:
            return _err("No window")
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if result and len(result) > 0:
            return _ok({"path": result[0]})
        return _ok({"cancelled": True})

    # ── Config ──

    def get_config(self) -> dict:
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return _ok(json.load(f))
            except Exception as e:
                log.warning("Failed to load config: %s", e)
        return _ok({})

    def save_config(self, data: dict) -> dict:
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return _ok()
        except Exception as e:
            log.warning("Failed to save config: %s", e)
            return _err(str(e))

    def set_tool_paths(self, hc_path: str, jtr_path: str) -> dict:
        if hc_path:
            if not tool_paths.set_hashcat_dir(hc_path):
                # Fallback: set path directly if validation fails (user chose it manually)
                tool_paths.hashcat_dir = Path(hc_path)
                tool_paths.hashcat_exe = Path(hc_path) / "hashcat.exe"
        else:
            tool_paths.hashcat_dir = None
            tool_paths.hashcat_exe = None

        if jtr_path:
            if not tool_paths.set_jtr_dir(jtr_path):
                tool_paths.jtr_dir = Path(jtr_path)
        else:
            tool_paths.jtr_dir = None

        self._sync_engine_paths()
        return _ok()

    # ── Potfile ──

    def get_potfile(self) -> dict:
        if not tool_paths.hashcat_dir:
            return _ok([])
        pot_path = tool_paths.hashcat_dir / "hashcat.potfile"
        if not pot_path.exists():
            return _ok([])
        entries = []
        try:
            with open(pot_path, "r", encoding="utf-8", errors="replace") as f:
                lines = [line.strip() for line in f if line.strip()]
                for line in reversed(lines):
                    if ":" in line:
                        h, p = line.rsplit(":", 1)
                        if h and p:  # skip malformed lines
                            entries.append({"hash": h, "password": p})
        except Exception:
            pass
        return _ok(entries)

    def clear_potfile(self) -> dict:
        if tool_paths.hashcat_dir:
            pot_path = tool_paths.hashcat_dir / "hashcat.potfile"
            if pot_path.exists():
                pot_path.unlink()
        return _ok()

    # ── Window Management ──

    def minimize(self):
        if self._window:
            self._window.minimize()

    def toggle_maximize(self) -> dict:
        if not self._window:
            return _ok({"maximized": False})

        # We manually keep track of the max state 
        if not hasattr(self, '_is_maximized'):
            self._is_maximized = False

        if self._is_maximized:
            self._window.restore()
            self._is_maximized = False
        else:
            self._window.maximize()
            self._is_maximized = True

        return _ok({"maximized": self._is_maximized})

    def get_window_size(self) -> dict:
        if self._window:
            return _ok({"width": self._window.width, "height": self._window.height})
        return _ok({"width": 1100, "height": 750})

    def resize(self, width: int, height: int) -> dict:
        if self._window:
            self._window.resize(width, height)
        return _ok()

    def close(self):
        if self._window:
            self._window.destroy()
