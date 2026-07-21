import logging
import threading

log = logging.getLogger(__name__)

def _ok(data=None):
    if data is None:
        data = {}
    return {"success": True, "data": data, "error": None}

def _err(msg):
    return {"success": False, "data": None, "error": msg}

class CrackMixin:
    """Kırma (Crack) işlemleri mixin'i."""

    def get_devices(self) -> dict:
        try:
            if not hasattr(self, "_crack_manager"):
                return _ok([])
            devs = self._crack_manager.get_devices()
            res = [{"id": d[0], "name": d[1]} for d in devs]
            return _ok(res)
        except Exception as e:
            log.warning("get_devices failed: %s", e)
            return _ok([])

    def run_benchmark(self, device_id: str) -> dict:
        if self._crack_manager.is_running:
            if hasattr(self, "_error_response"):
                return self._error_response("Engine is currently running.")
            return _err("Engine is currently running.")

        def _out(line):
            self._emit_event({"type": "info", "data": {"message": line.strip()}})

        def _done():
            self._emit_event({"type": "success", "data": {"message": "Benchmark complete."}})
            self._emit_event({"type": "status", "data": {"status": "Stopped"}})

        threading.Thread(
            target=self._crack_manager.run_benchmark,
            args=(device_id, _out, _done),
            daemon=True
        ).start()
        return _ok({"status": "running"})

    def run_restore(self, session_name: str) -> dict:
        if self._crack_manager.is_running:
            if hasattr(self, "_error_response"):
                return self._error_response("Engine is currently running.")
            return _err("Engine is currently running.")

        self._emit_event({"type": "separator"})
        self._emit_event({"type": "session_start", "data": {"version": "Restore Mode"}})
        self._emit_event({"type": "status", "data": {"status": "Starting..."}})
        self._crack_manager.mark_starting()

        def _out(line):
            if self._crack_manager.running_engine_name == "jtr":
                from core.jtr_event_parser import parse_jtr_line
                ev = parse_jtr_line(line)
            else:
                from core.hc_event_parser import parse_hc_line
                ev = parse_hc_line(line)
            if ev:
                self._emit_event(ev)

        def _done():
            self._emit_event({"type": "status", "data": {"status": "Stopped"}})

        threading.Thread(
            target=self._crack_manager.run_restore,
            args=(session_name, _out, _done),
            daemon=True
        ).start()

        return _ok({"status": "running"})

    def run_crack(
        self, hash_val: str, m_val: str, settings: dict
    ) -> dict:
        if self._crack_manager.is_running:
            if hasattr(self, "_error_response"):
                return self._error_response("Engine is already running. Please stop it first.")
            return _err("Engine is already running.")

        engine_choice = settings.get("engine", "hashcat")
        self._emit_event({"type": "separator"})
        self._emit_event({"type": "session_start", "data": {"version": f"{engine_choice.title()} Engine"}})
        self._emit_event({"type": "status", "data": {"status": "Starting..."}})

        # God Node fix: UI Manager starts the engine, passes callbacks
        self._crack_manager.mark_starting()

        def _out(line):
            if self._crack_manager.running_engine_name == "jtr":
                from core.jtr_event_parser import parse_jtr_line
                ev = parse_jtr_line(line)
            else:
                from core.hc_event_parser import parse_hc_line
                ev = parse_hc_line(line)
            if ev:
                self._emit_event(ev)

        def _done():
            self._emit_event({"type": "status", "data": {"status": "Stopped"}})

        threading.Thread(
            target=self._crack_manager.run_crack,
            args=(hash_val, m_val, settings, _out, _done),
            daemon=True
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
        self._crack_manager.checkpoint()
        self._emit_event({"type": "info", "data": {"message": "Checkpoint requested."}})
        return _ok()
