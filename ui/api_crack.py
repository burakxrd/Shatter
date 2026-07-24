import logging
import os
import threading

log = logging.getLogger(__name__)

from ui.envelope import _ok, _err


class CrackMixin:
    """Cracking operations mixin."""

    # ------------------------------------------------------------------ #
    # Shared helpers                                                       #
    # ------------------------------------------------------------------ #

    def _make_output_callback(self):
        """Return the line-by-line output callback used by both crack and restore."""
        def _out(line):
            if self._crack_manager.running_engine_name == "jtr":
                from core.jtr_event_parser import parse_jtr_line
                ev = parse_jtr_line(line)
            else:
                from core.hc_event_parser import parse_hc_line
                ev = parse_hc_line(line)
            if ev:
                self._emit_event(ev)
        return _out

    def _make_done_callback(self):
        """Return the on-done callback used by both crack and restore.

        After the engine exits it checks whether a restore file was actually
        written to disk (= checkpoint was honoured) and emits the appropriate
        events before signalling 'Stopped'.
        """
        def _done():
            session_name, restore_path = self._crack_manager.last_session_info
            if restore_path and os.path.isfile(restore_path):
                self._emit_event({"type": "success", "data": {
                    "message": f"Session saved: \"{session_name}\"  \u2192  {restore_path}"
                }})
            self._emit_event({"type": "status", "data": {"status": "Stopped"}})
        return _done

    def _engine_running_error(self):
        """Return a standardised 'already running' error response."""
        debug = (
            f"hc={self._crack_manager.hc_engine.is_running} "
            f"jtr={self._crack_manager.jtr_engine.is_running} "
            f"starting={self._crack_manager._starting}"
        )
        msg = f"Engine is already running. Please stop it first. ({debug})"
        if hasattr(self, "_error_response"):
            return self._error_response(msg)
        return _err(msg)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def get_devices(self) -> dict:
        try:
            if not hasattr(self, "_crack_manager"):
                return _ok([])
            devs = self._crack_manager.get_devices()
            return _ok([{"id": d[0], "name": d[1]} for d in devs])
        except Exception as e:
            log.warning("get_devices failed: %s", e)
            return _ok([])

    def run_benchmark(self, device_id: str) -> dict:
        if self._crack_manager.is_running:
            return self._engine_running_error()

        def _out(line):
            self._emit_event({"type": "info", "data": {"message": line.strip()}})

        def _done():
            self._emit_event({"type": "success", "data": {"message": "Benchmark complete."}})
            self._emit_event({"type": "status", "data": {"status": "Stopped"}})

        threading.Thread(
            target=self._crack_manager.run_benchmark,
            args=(device_id, _out, _done),
            daemon=True,
        ).start()
        return _ok({"status": "running"})

    def run_restore(self, restore_file_path: str) -> dict:
        if self._crack_manager.is_running:
            return self._engine_running_error()

        if not restore_file_path or not os.path.isfile(restore_file_path):
            msg = f"Restore file not found: {restore_file_path}"
            if hasattr(self, "_error_response"):
                return self._error_response(msg)
            return _err(msg)

        session_name = os.path.splitext(os.path.basename(restore_file_path))[0]

        self._emit_event({"type": "separator"})
        self._emit_event({"type": "session_start", "data": {"version": "Restore Mode"}})
        self._emit_event({"type": "status", "data": {"status": "Starting..."}})
        self._emit_event({"type": "info", "data": {"message": f"Restoring session: {session_name}"}})
        self._emit_event({"type": "info", "data": {"message": f"Restore file: {restore_file_path}"}})
        self._crack_manager.mark_starting()

        threading.Thread(
            target=self._crack_manager.run_restore,
            args=(session_name, restore_file_path,
                  self._make_output_callback(), self._make_done_callback()),
            daemon=True,
        ).start()
        return _ok({"status": "running"})

    def run_crack(self, hash_val: str, m_val: str, settings: dict) -> dict:
        if self._crack_manager.is_running:
            return self._engine_running_error()

        engine_choice = settings.get("engine", "hashcat")
        self._emit_event({"type": "separator"})
        self._emit_event({"type": "session_start", "data": {"version": f"{engine_choice.title()} Engine"}})
        self._emit_event({"type": "status", "data": {"status": "Starting..."}})
        self._crack_manager.mark_starting()

        threading.Thread(
            target=self._crack_manager.run_crack,
            args=(hash_val, m_val, settings,
                  self._make_output_callback(), self._make_done_callback()),
            daemon=True,
        ).start()
        return _ok({"status": "running"})

    def stop_crack(self) -> dict:
        self._crack_manager.stop()
        return _ok()

    def pause_crack(self) -> dict:
        ok = self._crack_manager.pause()
        if ok:
            self._emit_event({"type": "status", "data": {"status": "Paused"}})
        return _ok({"paused": ok})

    def resume_crack(self) -> dict:
        ok = self._crack_manager.resume()
        if ok:
            self._emit_event({"type": "status", "data": {"status": "Running"}})
        return _ok({"resumed": ok})

    def checkpoint_crack(self) -> dict:
        session_name, restore_path = self._crack_manager.last_session_info
        self._crack_manager.checkpoint()
        if restore_path:
            self._emit_event({"type": "info", "data": {
                "message": f"Checkpoint requested \u2014 saving to: {restore_path}"
            }})
        else:
            self._emit_event({"type": "info", "data": {"message": "Checkpoint requested."}})
        return _ok()
