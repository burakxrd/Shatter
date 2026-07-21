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
from core.hc_event_parser import parse_hc_line
from core.jtr_event_parser import parse_jtr_line
from core.detector import detect_hash_type
from core import APP_ROOT, TEMP_DIR
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
#  API Class
# ──────────────────────────────────────────────

class Api:
    def __init__(self):
        self._window: webview.Window | None = None
        self._downloading = False
        self._cancel_download = threading.Event()
        
        self._crack_manager = CrackManager()
        self._sync_engine_paths()

    # ── Internal Helpers ──

    def _sync_engine_paths(self):
        """Keep engine paths in sync with tool_paths module state."""
        self._crack_manager.set_tool_paths(tool_paths.hashcat_dir, tool_paths.jtr_dir)

    def _on_engine_output(self, line: str):
        engine_name = self._crack_manager.active_engine_name
        
        if engine_name == "jtr":
            event = parse_jtr_line(line)
        else:
            event = parse_hc_line(line)
            
        if event and self._window:
            safe = json.dumps(event)
            # The frontend currently expects onHashcatEvent. 
            # We will continue using it for both engines, since the event structure is identical.
            self._window.evaluate_js(f"onHashcatEvent({safe})")
                
    def _on_crack_done(self):
        if self._window:
            self._window.evaluate_js("onCrackDone()")

    # ── Hash Detection & Extraction ──

    def _error_response(self, message: str) -> dict:
        self._on_engine_output(f"[!] {message}")
        return _err(message)

    def detect_hash(self, hash_value: str) -> dict:
        from core.detector import extract_m_value
        algo = detect_hash_type(hash_value)
        m_value = extract_m_value(algo) or "0"
        return _ok({"algo": algo, "m_value": m_value})

    def extract_hash(self) -> dict:
        if not self._window:
            return self._error_response("No window")
        result = self._window.create_file_dialog(webview.OPEN_DIALOG)
        if result and len(result) > 0:
            path = result[0]
            self._sync_engine_paths()
            
            # Use the new shared extractor
            jtr_dir = tool_paths.jtr_dir
            if not jtr_dir:
                return self._error_response("John the Ripper is not configured. Go to General -> Tool Paths.")
                
            res = extract_hash_from_file(path, jtr_dir)
            if res.get("error"):
                return self._error_response(res["error"])
                
            return _ok({"hash": res["hash"], "engine": res["engine"]})
            
        return _ok({"cancelled": True})

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

    # ── Crack Operations ──

    def start_crack(self, settings: dict) -> dict:
        self._sync_engine_paths()
        if self._crack_manager.is_running:
            return self._error_response("Engine is already running.")

        hash_val = settings.get("hash", "")
        m_val = settings.get("m_value", "0")

        # Clear log on start
        if self._window:
            self._window.evaluate_js("clearHashcatOutput()")

        threading.Thread(
            target=self._crack_manager.run_crack,
            args=(hash_val, m_val, settings, self._on_engine_output, self._on_crack_done),
            daemon=True
        ).start()

        return _ok({"status": "started"})

    def restore_crack(self, session_name: str) -> dict:
        self._sync_engine_paths()
        if self._crack_manager.is_running:
            return self._error_response("Engine is already running.")

        if self._window:
            self._window.evaluate_js("clearHashcatOutput()")

        threading.Thread(
            target=self._crack_manager.run_restore,
            args=(session_name, self._on_engine_output, self._on_crack_done),
            daemon=True
        ).start()
        return _ok({"status": "restoring"})

    def stop_crack(self) -> dict:
        self._crack_manager.stop()
        return _ok()

    def pause_crack(self) -> dict:
        if self._crack_manager.is_paused:
            self._crack_manager.resume()
            return _ok({"paused": False})
        else:
            self._crack_manager.pause()
            return _ok({"paused": True})

    def checkpoint_crack(self) -> dict:
        self._crack_manager.checkpoint()
        return _ok()

    def get_devices(self) -> dict:
        self._sync_engine_paths()
        devices = self._crack_manager.get_devices()
        return _ok([{"id": d[0], "name": d[1]} for d in devices])

    def run_benchmark(self, device_id: str) -> dict:
        self._sync_engine_paths()
        if self._crack_manager.is_running:
            return self._error_response("Wait for active run to finish.")

        if self._window:
            self._window.evaluate_js("clearHashcatOutput()")

        threading.Thread(
            target=self._crack_manager.run_benchmark,
            args=(device_id, self._on_engine_output, self._on_crack_done),
            daemon=True
        ).start()
        return _ok({"status": "started"})

    # ── File / Folder Dialogs ──

    def browse_folder(self) -> dict:
        if not self._window:
            return self._error_response("No window")
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
            return self._error_response(str(e))

    def set_tool_paths(self, hc_path: str, jtr_path: str) -> dict:
        if hc_path:
            if not tool_paths.set_hashcat_dir(hc_path):
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

    # ── Tool Downloads ──

    def download_hashcat(self) -> dict:
        if self._downloading:
            return self._error_response("A download is already in progress.")
        self._downloading = True
        self._cancel_download.clear()

        def _do():
            try:
                from core.downloader import download_hashcat as dl_hashcat
                dest = APP_ROOT / "hashcat"

                def on_progress(downloaded, total):
                    if self._window and total > 0:
                        pct = round(downloaded / total * 100, 1)
                        self._window.evaluate_js(
                            f"onDownloadProgress('hashcat', {pct}, {downloaded}, {total})"
                        )

                hc_dir = dl_hashcat(dest, on_progress, self._cancel_download.is_set)
                tool_paths.set_hashcat_dir(str(hc_dir))
                self._sync_engine_paths()

                if self._window:
                    safe_path = json.dumps(str(hc_dir))
                    self._window.evaluate_js(
                        f"onDownloadDone('hashcat', true, {safe_path})"
                    )
            except InterruptedError:
                log.info("Hashcat download cancelled by user.")
                if self._window:
                    self._window.evaluate_js(
                        "onDownloadDone('hashcat', false, 'Download cancelled.')"
                    )
            except Exception as e:
                log.exception("Hashcat download failed")
                if self._window:
                    safe_err = json.dumps(str(e))
                    self._window.evaluate_js(
                        f"onDownloadDone('hashcat', false, {safe_err})"
                    )
            finally:
                self._downloading = False

        threading.Thread(target=_do, daemon=True).start()
        return _ok({"status": "downloading"})

    def download_jtr(self) -> dict:
        if self._downloading:
            return self._error_response("A download is already in progress.")
        self._downloading = True
        self._cancel_download.clear()

        def _do():
            try:
                from core.downloader import download_jtr as dl_jtr
                dest = APP_ROOT / "johntheripper"

                def on_progress(downloaded, total):
                    if self._window and total > 0:
                        pct = round(downloaded / total * 100, 1)
                        self._window.evaluate_js(
                            f"onDownloadProgress('jtr', {pct}, {downloaded}, {total})"
                        )

                jtr_dir = dl_jtr(dest, on_progress, self._cancel_download.is_set)
                tool_paths.set_jtr_dir(str(jtr_dir))
                self._sync_engine_paths()

                if self._window:
                    safe_path = json.dumps(str(jtr_dir))
                    self._window.evaluate_js(
                        f"onDownloadDone('jtr', true, {safe_path})"
                    )
            except InterruptedError:
                log.info("JtR download cancelled by user.")
                if self._window:
                    self._window.evaluate_js(
                        "onDownloadDone('jtr', false, 'Download cancelled.')"
                    )
            except Exception as e:
                log.exception("JtR download failed")
                if self._window:
                    safe_err = json.dumps(str(e))
                    self._window.evaluate_js(
                        f"onDownloadDone('jtr', false, {safe_err})"
                    )
            finally:
                self._downloading = False

        threading.Thread(target=_do, daemon=True).start()
        return _ok({"status": "downloading"})

    def cancel_download(self) -> dict:
        self._cancel_download.set()
        return _ok()


    # ── Potfile ──

    def get_potfile(self) -> dict:
        # Only querying Hashcat's potfile for UI right now
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
                        if h and p:
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
