"""
api.py — Python-to-JS Bridge for Shatter (pywebview).
"""

import json
import logging
import threading
from pathlib import Path
import webview

from core.engine import (
    extract_hash_from_file,
    get_devices,
    run_hashcat,
    run_benchmark,
    run_hashcat_restore,
    hashcat_stop,
    hashcat_pause,
    hashcat_resume,
    hashcat_checkpoint,
    is_hashcat_running,
    is_hashcat_paused,
)
from core.detector import detect_hash_type
from core import TEMP_DIR
import core.tool_paths as tool_paths

log = logging.getLogger(__name__)
CONFIG_FILE = TEMP_DIR / "config.json"

_NOISE_PREFIXES = (
    "Minimum password", "Maximum password",
    "Minimum salt length", "Maximum salt length",
    "Optimizers applied", "Watchdog:", "Hashes:", "Bitmaps:", "Rules:",
    "CUDA API", "OpenCL API",
    "Kernel.Feature", "Guess.Queue", "Rejected",
    "Restore.Point", "Restore.Sub", "Candidate.Engine",
    "Candidates.#", "Hardware.Mon",
    "ATTENTION!", "Pure kernels", "If you want to switch",
    "See the above message",
    "Started:", "Stopped:",
    "[*] Command:",
    "Dictionary cache",
)
_NOISE_CONTAINS = ("Please be patient", "nvmlDeviceGetFanSpeed")

def _is_output_noise(line: str) -> bool:
    """Return True if this line should be hidden from the Event Log."""
    s = line.strip()
    if not s or s.startswith("===="):
        return True
    if s.startswith("* "):
        keep = (
            (s.startswith("* Device") and "skipped" not in s)
            or s.startswith("* Filename")
            or s.startswith("* Passwords")
        )
        return not keep
    for kw in _NOISE_CONTAINS:
        if kw in s:
            return True
    return s.startswith(_NOISE_PREFIXES)


class Api:
    def __init__(self):
        self._window: webview.Window | None = None
        
    def _on_hashcat_output(self, line: str):
        if not _is_output_noise(line):
            if self._window:
                escaped = line.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '')
                self._window.evaluate_js(f"onHashcatOutput('{escaped}')")
                
    def _on_crack_done(self):
        if self._window:
            self._window.evaluate_js("onCrackDone()")

    def detect_hash(self, hash_value: str) -> dict:
        from core.detector import extract_m_value
        algo = detect_hash_type(hash_value)
        m_value = extract_m_value(algo) or "0"
        return {"algo": algo, "m_value": m_value}

    def extract_hash(self) -> dict:
        if not self._window:
            return {"error": "No window"}
        result = self._window.create_file_dialog(webview.OPEN_DIALOG)
        if result and len(result) > 0:
            path = result[0]
            extracted = extract_hash_from_file(path)
            if extracted.startswith("[!]"):
                return {"error": extracted}
            return {"hash": extracted}
        return {"cancelled": True}

    def load_hash_file(self) -> dict:
        if not self._window:
            return {"error": "No window"}
        result = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=("Text Files (*.txt)|*.txt", "All Files (*.*)|*.*"))
        if result and len(result) > 0:
            return {"path": result[0]}
        return {"cancelled": True}

    def select_wordlist(self) -> dict:
        if not self._window:
            return {"error": "No window"}
        result = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=("Text Files (*.txt)|*.txt", "All Files (*.*)|*.*"))
        if result and len(result) > 0:
            return {"path": result[0]}
        return {"cancelled": True}

    def add_rule(self) -> dict:
        if not self._window:
            return {"error": "No window"}
        result = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=("Rule Files (*.rule)|*.rule", "All Files (*.*)|*.*"))
        if result and len(result) > 0:
            return {"path": result[0]}
        return {"cancelled": True}

    def start_crack(self, settings: dict) -> dict:
        if is_hashcat_running():
            return {"error": "Hashcat is already running."}
        
        hash_val = settings.get("hash", "")
        m_val = settings.get("m_value", "0")
        
        # Clear log on start
        if self._window:
            self._window.evaluate_js("clearHashcatOutput()")
            
        threading.Thread(
            target=run_hashcat,
            args=(hash_val, m_val, settings, self._on_hashcat_output, self._on_crack_done),
            daemon=True
        ).start()
        
        return {"status": "started"}

    def restore_crack(self, session_name: str) -> dict:
        if is_hashcat_running():
            return {"error": "Hashcat is already running."}
            
        if self._window:
            self._window.evaluate_js("clearHashcatOutput()")
            
        threading.Thread(
            target=run_hashcat_restore,
            args=(session_name, self._on_hashcat_output, self._on_crack_done),
            daemon=True
        ).start()
        return {"status": "restoring"}

    def stop_crack(self):
        hashcat_stop()

    def pause_crack(self) -> bool:
        if is_hashcat_paused():
            return hashcat_resume()
        else:
            return hashcat_pause()

    def checkpoint_crack(self):
        hashcat_checkpoint()
        
    def get_devices(self) -> list:
        return [{"id": d[0], "name": d[1]} for d in get_devices()]

    def run_benchmark(self, device_id: str) -> dict:
        if is_hashcat_running():
            return {"error": "Wait for active run to finish."}
            
        if self._window:
            self._window.evaluate_js("clearHashcatOutput()")
            
        threading.Thread(
            target=run_benchmark,
            args=(device_id, self._on_hashcat_output, self._on_crack_done),
            daemon=True
        ).start()
        return {"status": "started"}

    def browse_folder(self) -> dict:
        if not self._window:
            return {"error": "No window"}
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if result and len(result) > 0:
            return {"path": result[0]}
        return {"cancelled": True}

    def get_config(self) -> dict:
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                log.warning("Failed to load config: %s", e)
        return {}

    def save_config(self, data: dict):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            log.warning("Failed to save config: %s", e)

    def set_tool_paths(self, hc_path: str, jtr_path: str):
        tool_paths.hashcat_dir = Path(hc_path) if hc_path else None
        if tool_paths.hashcat_dir:
            tool_paths.hashcat_exe = tool_paths.hashcat_dir / "hashcat.exe"
        else:
            tool_paths.hashcat_exe = None

        tool_paths.jtr_dir = Path(jtr_path) if jtr_path else None

    def get_potfile(self) -> list:
        if not tool_paths.hashcat_dir:
            return []
        pot_path = tool_paths.hashcat_dir / "hashcat.potfile"
        if not pot_path.exists():
            return []
        entries = []
        try:
            with open(pot_path, "r", encoding="utf-8", errors="replace") as f:
                lines = [line.strip() for line in f if line.strip()]
                for line in reversed(lines):
                    if ":" in line:
                        h, p = line.rsplit(":", 1)
                        entries.append({"hash": h, "password": p})
        except Exception:
            pass
        return entries

    def clear_potfile(self):
        if tool_paths.hashcat_dir:
            pot_path = tool_paths.hashcat_dir / "hashcat.potfile"
            if pot_path.exists():
                pot_path.unlink()

    def minimize(self):
        if self._window:
            self._window.minimize()

    def toggle_maximize(self) -> bool:
        if not self._window:
            return False
        
        # We manually keep track of the max state 
        if not hasattr(self, '_is_maximized'):
            self._is_maximized = False
            
        if self._is_maximized:
            self._window.restore()
            self._is_maximized = False
        else:
            self._window.maximize()
            self._is_maximized = True
            
        return self._is_maximized

    def get_window_size(self) -> dict:
        if self._window:
            return {"width": self._window.width, "height": self._window.height}
        return {"width": 1100, "height": 750}

    def resize(self, width: int, height: int):
        if self._window:
            self._window.resize(width, height)

    def close(self):
        if self._window:
            self._window.destroy()
