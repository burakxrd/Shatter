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

from core.crack_manager import CrackManager
from core.extractor import extract_hash_from_file
from core.detector import detect_hash_type
from core import APP_ROOT, TEMP_DIR
import core.tool_paths as tool_paths

from ui.api_config import ConfigMixin
from ui.api_download import DownloadMixin
from ui.api_crack import CrackMixin

log = logging.getLogger(__name__)
CONFIG_FILE = TEMP_DIR / "config.json"


def _ok(data=None) -> dict:
    if data is None:
        data = {}
    return {"success": True, "data": data, "error": None}

def _err(message: str) -> dict:
    return {"success": False, "data": None, "error": message}


class Api(ConfigMixin, DownloadMixin, CrackMixin):
    def __init__(self):
        super().__init__()
        self._window: webview.Window | None = None
        
        self._crack_manager = CrackManager()
        self._sync_engine_paths()

        self._pending_events: list[dict] = []
        self._flush_timer: threading.Timer | None = None
        self._flush_lock = threading.Lock()
        self._FLUSH_INTERVAL = 0.05

    def set_window(self, window: webview.Window):
        self._window = window

    def _sync_engine_paths(self):
        self._crack_manager.set_tool_paths(tool_paths.hashcat_dir, tool_paths.jtr_dir)

    def _emit_event(self, event: dict):
        if not self._window:
            return
        with self._flush_lock:
            self._pending_events.append(event)
            if self._flush_timer is None:
                self._flush_timer = threading.Timer(
                    self._FLUSH_INTERVAL, self._flush_events
                )
                self._flush_timer.daemon = True
                self._flush_timer.start()

    def _flush_events(self):
        with self._flush_lock:
            events_to_send = self._pending_events
            self._pending_events = []
            self._flush_timer = None

        if events_to_send and self._window:
            try:
                js_code = f"if (window.onHashcatEvent) {{ {json.dumps(events_to_send)}.forEach(e => window.onHashcatEvent(e)); }}"
                self._window.evaluate_js(js_code)
            except Exception as e:
                log.error("Failed to push events to JS: %s", e)

    def _error_response(self, message: str) -> dict:
        self._emit_event({"type": "error", "data": {"message": message}})
        return _err(message)

    # ── Hash Detection & Extraction ──

    def detect_hash(self, hash_value: str) -> dict:
        from core.detector import extract_m_value
        algo = detect_hash_type(hash_value)
        m_value = extract_m_value(algo)
        return _ok({
            "algo": algo, 
            "m_value": m_value,
            "needs_manual_selection": m_value is None
        })

    def extract_hash(self) -> dict:
        if not self._window:
            return self._error_response("No window")
        result = self._window.create_file_dialog(webview.OPEN_DIALOG)
        if not result or len(result) == 0:
            return _ok({"cancelled": True})

        path = result[0]
        self._sync_engine_paths()
        
        jtr_dir = tool_paths.jtr_dir
        if not jtr_dir:
            return self._error_response("John the Ripper is not configured. Go to General -> Tool Paths.")

        def _extract_task():
            try:
                res = extract_hash_from_file(path, jtr_dir)
                self._emit_event({
                    "type": "extract_done",
                    "data": {"hash": res.data, "engine": res.engine, "error": res.error}
                })
            except Exception as e:
                self._emit_event({
                    "type": "error",
                    "data": {"message": f"Extraction failed: {e}"}
                })

        threading.Thread(target=_extract_task, daemon=True).start()
        return _ok({"status": "extracting", "cancelled": False})

    def load_hash_file(self) -> dict:
        if not self._window:
            return self._error_response("No window")
        result = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=("Text Files (*.txt)", "All Files (*.*)"))
        if result and len(result) > 0:
            return _ok({"path": result[0]})
        return _ok({"cancelled": True})

    def select_wordlist(self) -> dict:
        if not self._window:
            return self._error_response("No window")
        result = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=("Text Files (*.txt)", "All Files (*.*)"))
        if result and len(result) > 0:
            return _ok({"path": result[0]})
        return _ok({"cancelled": True})

    def add_rule(self) -> dict:
        if not self._window:
            return self._error_response("No window")
        result = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=("Rule Files (*.rule)", "All Files (*.*)"))
        if result and len(result) > 0:
            return _ok({"path": result[0]})
        return _ok({"cancelled": True})

    def browse_folder(self) -> dict:
        if not self._window:
            return self._error_response("No window")
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if result and len(result) > 0:
            return _ok({"path": result[0]})
        return _ok({"cancelled": True})

    # ── Legacy Crack Aliases for JS ──
    # app.js uses start_crack, restore_crack, is_running
    def start_crack(self, settings: dict) -> dict:
        hash_val = settings.get("hash", "")
        m_val = settings.get("m_value", "0")
        if self._window:
            self._window.evaluate_js("clearHashcatOutput()")
        return self.run_crack(hash_val, m_val, settings)

    def restore_crack(self, session_name: str) -> dict:
        if self._window:
            self._window.evaluate_js("clearHashcatOutput()")
        return self.run_restore(session_name)

    def is_running(self) -> dict:
        return _ok(self._crack_manager.is_running)

    # ── Potfile ──

    def get_potfile(self) -> dict:
        from core.potfile_parser import parse_hashcat_potfile, parse_jtr_potfile
        entries = []
        seen = set()

        if tool_paths.hashcat_dir:
            hc_pot = tool_paths.hashcat_dir / "hashcat.potfile"
            for entry in parse_hashcat_potfile(hc_pot):
                key = (entry["hash"], entry["password"])
                if key not in seen:
                    seen.add(key)
                    entries.append(entry)

        if tool_paths.jtr_dir:
            jtr_pot = tool_paths.jtr_dir / "john.pot"
            if not jtr_pot.exists():
                jtr_pot = tool_paths.jtr_dir / "run" / "john.pot"
            for entry in parse_jtr_potfile(jtr_pot):
                key = (entry["hash"], entry["password"])
                if key not in seen:
                    seen.add(key)
                    entries.append(entry)

        return _ok(entries)

    def clear_potfile(self) -> dict:
        if tool_paths.hashcat_dir:
            pot_path = tool_paths.hashcat_dir / "hashcat.potfile"
            if pot_path.exists():
                pot_path.unlink(missing_ok=True)
        if tool_paths.jtr_dir:
            jtr_pot = tool_paths.jtr_dir / "john.pot"
            if not jtr_pot.exists():
                jtr_pot = tool_paths.jtr_dir / "run" / "john.pot"
            if jtr_pot.exists():
                jtr_pot.unlink(missing_ok=True)
        return _ok()

    # ── Window Management ──

    def minimize(self):
        if self._window:
            self._window.minimize()

    def toggle_maximize(self) -> dict:
        if not self._window:
            return _ok({"maximized": False})

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
