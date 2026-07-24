import logging
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
import psutil

log = logging.getLogger(__name__)

_TRACKED_NAMES = {"hashcat", "hashcat.exe", "john", "john.exe"}
_PSUTIL_CACHE_TTL = 1.0  # seconds

class ManagedProcess:
    """
    Manages a subprocess lifecycle (start, pause, resume, checkpoint, kill).
    Generic enough to run Hashcat, John the Ripper, or any other binary.
    """
    def __init__(self):
        self._active_proc: subprocess.Popen | None = None
        self._paused: bool = False
        self._proc_lock = threading.Lock()
        self._psutil_cache_ts: float = 0.0
        self._psutil_cache_result: bool = False

    def stream_process(
        self,
        cmd: list[str],
        cwd: str | Path,
        on_output: Callable[[str], None],
        on_done: Callable[[], None],
        *,
        creation_flags: int = 0,
        store_proc: bool = False,
    ) -> int:
        """Run a subprocess and stream its stdout line-by-line."""
        try:
            # On Windows: hide the console window via STARTUPINFO instead of
            # CREATE_NO_WINDOW.  CREATE_NO_WINDOW detaches the process from any
            # console, which prevents hashcat's SetConsoleCtrlHandler from
            # receiving CTRL_BREAK_EVENT (used for graceful checkpoint quit).
            # SW_HIDE keeps the console alive (so the handler works) while
            # still not showing a visible window to the user.
            kwargs: dict = {}
            if sys.platform == "win32":
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = 0  # SW_HIDE
                kwargs["startupinfo"] = si

            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                errors="replace",
                creationflags=creation_flags,
                **kwargs,
            )

            if store_proc:
                with self._proc_lock:
                    if self._active_proc is not None and self._active_proc.poll() is None:
                        proc.kill()
                        on_output("[!] Another process is already running.\n")
                        on_done()
                        return -1
                    self._active_proc = proc
                    self._paused = False

            for line in proc.stdout:  # type: ignore[union-attr]
                on_output(line)

            proc.wait()
            return proc.returncode

        except FileNotFoundError:
            on_output(f"[!] Executable not found: {cmd[0]}\n")
            return -1
        except Exception as e:
            on_output(f"[!] Process error: {e}\n")
            return -1
        finally:
            if store_proc:
                with self._proc_lock:
                    self._active_proc = None
                    self._paused = False
            try:
                on_done()
            except Exception as e:
                log.error("on_done callback raised an exception: %s", e)

    @staticmethod
    def run_quiet(cmd: list[str], cwd: str | Path, timeout: int = 15) -> subprocess.CompletedProcess:
        """Run a subprocess quietly and return the result. No streaming."""
        kwargs: dict = {}
        if sys.platform == "win32":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0  # SW_HIDE
            kwargs["startupinfo"] = si
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            errors="replace",
            **kwargs,
        )

    def stop(self) -> None:
        """Kill the active process immediately."""
        proc = self._active_proc
        if proc is None or proc.poll() is not None:
            return
        try:
            if self._paused:
                psutil.Process(proc.pid).resume()
                self._paused = False
            proc.kill()
            log.info("Process killed.")
        except Exception as e:
            log.warning("Failed to stop process: %s", e)

    def pause(self) -> bool:
        """Suspend the process. Returns True if paused successfully."""
        proc = self._active_proc
        if proc is None or proc.poll() is not None or self._paused:
            return False
        try:
            psutil.Process(proc.pid).suspend()
            self._paused = True
            log.info("Process paused.")
            return True
        except Exception as e:
            log.warning("Failed to pause process: %s", e)
            return False

    def resume(self) -> bool:
        """Resume a paused process. Returns True if resumed successfully."""
        proc = self._active_proc
        if proc is None or proc.poll() is not None or not self._paused:
            return False
        try:
            psutil.Process(proc.pid).resume()
            self._paused = False
            log.info("Process resumed.")
            return True
        except Exception as e:
            log.warning("Failed to resume process: %s", e)
            return False

    def checkpoint(self) -> None:
        """
        Send CTRL_BREAK to process for graceful shutdown with state save.
        """
        proc = self._active_proc
        if proc is None or proc.poll() is not None:
            return
        try:
            if self._paused:
                psutil.Process(proc.pid).resume()
                self._paused = False
            if sys.platform == "win32":
                # os.kill with CTRL_BREAK_EVENT works reliably with
                # CREATE_NEW_PROCESS_GROUP even when CREATE_NO_WINDOW is set,
                # unlike GenerateConsoleCtrlEvent which needs a console.
                os.kill(proc.pid, signal.CTRL_BREAK_EVENT)
            else:
                proc.send_signal(signal.SIGINT)
            log.info("Checkpoint signal sent.")
        except Exception as e:
            log.warning("Failed to checkpoint process: %s", e)
            try:
                proc.kill()
            except Exception:
                pass

    @property
    def is_running(self) -> bool:
        """Check if a process is currently active (own proc OR any system-wide hashcat/john)."""
        # 1. Own managed process — cheap check, always first
        if self._active_proc is not None and self._active_proc.poll() is None:
            return True
        # 2. System-wide check — cached to avoid scanning all processes on every poll
        now = time.monotonic()
        if now - self._psutil_cache_ts < _PSUTIL_CACHE_TTL:
            return self._psutil_cache_result
        result = False
        try:
            for proc in psutil.process_iter(["name"]):
                if proc.info["name"] and proc.info["name"].lower() in _TRACKED_NAMES:
                    result = True
                    break
        except Exception:
            pass
        self._psutil_cache_result = result
        self._psutil_cache_ts = now
        return result

    @property
    def is_paused(self) -> bool:
        """Check if the active process is paused."""
        return self._paused
