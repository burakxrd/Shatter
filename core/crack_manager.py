import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.hc_engine import HashcatEngine
from core.jtr_engine import JtrEngine

log = logging.getLogger(__name__)

class CrackManager:
    """Orchestrates between Hashcat and John the Ripper engines."""

    def __init__(self) -> None:
        self.hc_engine = HashcatEngine()
        self.jtr_engine = JtrEngine()
        self.active_engine_name = "hashcat"
        self._active_engine = self.hc_engine
        self._starting = False

    def _activate_engine(self, engine_name: str) -> None:
        """Safely switches the active engine."""
        if engine_name not in ("hashcat", "jtr"):
            raise ValueError(f"Unknown engine: {engine_name}")
        self.active_engine_name = engine_name
        self._active_engine = self.hc_engine if engine_name == "hashcat" else self.jtr_engine

    def set_tool_paths(self, hc_dir: Path | None, jtr_dir: Path | None) -> None:
        import sys
        self.hc_engine.hashcat_dir = hc_dir
        if hc_dir:
            exe_name = "hashcat.exe" if sys.platform == "win32" else "hashcat"
            exe_path = hc_dir / exe_name
            if exe_path.is_file():
                self.hc_engine.hashcat_exe = exe_path
            else:
                candidates = [
                    f for f in hc_dir.iterdir()
                    if f.is_file() and f.stem.lower() == "hashcat" and self._is_executable(f)
                ]
                if candidates:
                    self.hc_engine.hashcat_exe = candidates[0]
                else:
                    log.error("Hashcat executable not found in %s", hc_dir)

        self.jtr_engine.jtr_dir = jtr_dir
        if jtr_dir:
            exe_name = "john.exe" if sys.platform == "win32" else "john"
            run_dir = jtr_dir / "run"
            exe_path = run_dir / exe_name if run_dir.is_dir() else jtr_dir / exe_name
            if exe_path.is_file():
                self.jtr_engine.jtr_exe = exe_path
            else:
                log.error("John executable not found in %s", jtr_dir)

    def _is_executable(self, path: Path) -> bool:
        """Checks if the file is executable."""
        import os
        import sys
        if sys.platform == "win32":
            return path.suffix.lower() in (".exe", ".bat", ".cmd")
        return os.access(path, os.X_OK)

    def get_devices(self) -> list[tuple[str, str]]:
        # Only hashcat supports -I device listing
        return self.hc_engine.get_devices()

    def run_benchmark(self, device_id: str, on_output: Callable[[str], None], on_done: Callable[[], None]) -> None:
        self._activate_engine("hashcat")
        self.hc_engine.run_benchmark(device_id, on_output, on_done)

    def run_restore(self, session_name: str, restore_file_path: str, on_output: Callable[[str], None], on_done: Callable[[], None]) -> None:
        # Currently only supporting hashcat restore
        self._starting = True
        self._activate_engine("hashcat")
        self.hc_engine.run_restore(session_name, restore_file_path, on_output, lambda: self._on_engine_done(on_done))

    def stop(self) -> None:
        self._active_engine.stop()

    def pause(self) -> bool:
        return self._active_engine.pause()

    def resume(self) -> bool:
        return self._active_engine.resume()

    def checkpoint(self) -> None:
        self._active_engine.checkpoint()

    def mark_starting(self) -> None:
        """Sets the 'starting' flag to prevent race conditions."""
        self._starting = True

    @property
    def is_running(self) -> bool:
        """Check if any engine is currently running."""
        return self.hc_engine.is_running or self.jtr_engine.is_running or self._starting

    @property
    def last_session_info(self) -> tuple[str | None, str | None]:
        """Returns (session_name, restore_file_path) from the last crack command."""
        rf = self.hc_engine._last_restore_file
        return (self.hc_engine._last_session, str(rf) if rf else None)

    @property
    def running_engine_name(self) -> str | None:
        """Returns the name of the running engine. None if none are running."""
        if self.hc_engine.is_running:
            return "hashcat"
        if self.jtr_engine.is_running:
            return "jtr"
        if self._starting:
            return self.active_engine_name

    @property
    def is_paused(self) -> bool:
        return self._active_engine.is_paused

    def run_crack(
        self,
        hash_value: str,
        m_value: str,
        settings: dict,
        on_output: Callable[[str], None],
        on_done: Callable[[], None],
    ) -> None:
        engine_choice = settings.get("engine", "hashcat")
        self._activate_engine(engine_choice)

        if engine_choice == "jtr":
            jtr_format = settings.get("jtr_format") 
            self.jtr_engine.run_crack(hash_value, jtr_format, settings, on_output, lambda: self._on_engine_done(on_done))
        else:
            self.hc_engine.run_crack(hash_value, m_value, settings, on_output, lambda: self._on_engine_done(on_done))

    def _on_engine_done(self, user_callback: Callable[[], None]) -> None:
        """Clean up state when the engine finishes."""
        self._starting = False
        user_callback()
