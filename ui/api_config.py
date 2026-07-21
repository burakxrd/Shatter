import json
import logging
import shutil
from pathlib import Path

from core import TEMP_DIR
import core.tool_paths as tool_paths

log = logging.getLogger(__name__)

CONFIG_FILE = TEMP_DIR / "config.json"

def _ok(data=None):
    if data is None:
        data = {}
    return {"success": True, "data": data, "error": None}

def _err(msg):
    return {"success": False, "data": None, "error": msg}

class ConfigMixin:
    """Konfigürasyon ve dizin yönetimi mixin'i."""

    def get_config(self) -> dict:
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return _ok(json.load(f))
            except (json.JSONDecodeError, OSError) as e:
                log.error("Corrupted config file: %s", e)
                backup_path = CONFIG_FILE.with_suffix(".json.bak")
                try:
                    shutil.move(str(CONFIG_FILE), str(backup_path))
                    log.info("Backed up corrupted config to %s", backup_path)
                except OSError:
                    pass
                if hasattr(self, "_emit_event"):
                    self._emit_event({
                        "type": "error",
                        "data": {"message": "Settings file was corrupted and has been reset to defaults."}
                    })
        return _ok({})

    def save_config(self, data: dict) -> dict:
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return _ok()
        except Exception as e:
            log.warning("Failed to save config: %s", e)
            if hasattr(self, "_error_response"):
                return self._error_response(str(e))
            return _err(str(e))

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

        if hasattr(self, "_sync_engine_paths"):
            self._sync_engine_paths()
        return _ok()
