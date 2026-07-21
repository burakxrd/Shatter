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

    def set_tool_paths(self, hc_dir: Path | None, jtr_dir: Path | None) -> None:
        self.hc_engine.hashcat_dir = hc_dir
        if hc_dir:
            self.hc_engine.hashcat_exe = hc_dir / ("hashcat.exe" if hc_dir.name != "hashcat" else "hashcat")
        self.jtr_engine.jtr_dir = jtr_dir

    @property
    def _active_engine(self) -> Any:
        if self.active_engine_name == "jtr":
            return self.jtr_engine
        return self.hc_engine

    def get_devices(self) -> list[tuple[str, str]]:
        # Only hashcat supports -I device listing
        return self.hc_engine.get_devices()

    def run_benchmark(self, device_id: str, on_output: Callable[[str], None], on_done: Callable[[], None]) -> None:
        self.hc_engine.run_benchmark(device_id, on_output, on_done)

    def run_restore(self, session_name: str, on_output: Callable[[str], None], on_done: Callable[[], None]) -> None:
        # Currently only supporting hashcat restore
        self.hc_engine.run_restore(session_name, on_output, on_done)

    def stop(self) -> None:
        self._active_engine.stop()

    def pause(self) -> bool:
        return self._active_engine.pause()

    def resume(self) -> bool:
        return self._active_engine.resume()

    def checkpoint(self) -> None:
        self._active_engine.checkpoint()

    @property
    def is_running(self) -> bool:
        return self._active_engine.is_running

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
        self.active_engine_name = engine_choice

        if engine_choice == "jtr":
            # For JtR, we can optionally parse JtR format from m_value if needed,
            # or we let JtR auto-detect by passing None.
            # We'll pass None for auto-detect for now unless explicitly specified.
            jtr_format = settings.get("jtr_format") 
            self.jtr_engine.run_crack(hash_value, jtr_format, settings, on_output, on_done)
        else:
            self.hc_engine.run_crack(hash_value, m_value, settings, on_output, on_done)
