"""
engine.py — Hashcat execution engine and hash extraction backend.

Handles:
- Hash extraction from encrypted files via *2john tools
- Native .cap/.pcap/.pcapng parsing via cap_parser
- Hashcat process management (crack, benchmark, show, device listing)
"""

import ctypes
import logging
import re
import signal
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psutil

from core.cap_parser import cap_to_hc22000_string
from core import TEMP_DIR


# ──────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────
log = logging.getLogger(__name__)

TARGET_HASH_FILE = TEMP_DIR / "target_hash.txt"

# Mapping: file extension -> (extractor tool, extra args)
HASH_EXTRACTORS: dict[str, tuple[str, list[str]]] = {
    ".zip":  ("zip2john.exe",     []),
    ".rar":  ("rar2john.exe",     []),
    ".7z":   ("7z2john.pl",   []),
    ".pdf":  ("pdf2john.pl",  []),
    ".docx": ("office2john.py",[]),
    ".xlsx": ("office2john.py",[]),
    ".pptx": ("office2john.py",[]),
    ".doc":  ("office2john.py",[]),
    ".xls":  ("office2john.py",[]),
    ".kdbx": ("keepass2john.exe",  []),
    ".ssh":  ("ssh2john.py",  []),
    ".gpg":  ("gpg2john.exe",     []),
    ".pfx":  ("pfx2john.py",  []),
}

# Extensions handled natively by cap_parser (not via *2john tools)
CAP_EXTENSIONS = {".cap", ".pcap", ".pcapng"}


# ──────────────────────────────────────────────
#  HashcatEngine Class
# ──────────────────────────────────────────────

class HashcatEngine:
    """Manages Hashcat process lifecycle and hash extraction.

    All process state is encapsulated within the instance, making it
    testable (easy to mock paths) and ready for multiple concurrent
    engines in the future.

    Args:
        hashcat_exe: Path to the hashcat executable.
        hashcat_dir: Directory containing hashcat (used as cwd).
        jtr_dir:     Directory containing John the Ripper run/ tools.
    """

    def __init__(
        self,
        hashcat_exe: Path | None = None,
        hashcat_dir: Path | None = None,
        jtr_dir: Path | None = None,
    ) -> None:
        self.hashcat_exe = hashcat_exe
        self.hashcat_dir = hashcat_dir
        self.jtr_dir = jtr_dir

        # Active hashcat process state
        self._active_proc: subprocess.Popen | None = None
        self._paused: bool = False
        self._proc_lock = threading.Lock()

    # ── Path Helpers ──

    def _get_hashcat_exe(self) -> Path:
        if self.hashcat_exe:
            return self.hashcat_exe
        raise FileNotFoundError("Hashcat not configured. Go to General → Tool Paths.")

    def _get_hashcat_cwd(self) -> Path:
        if self.hashcat_dir:
            return self.hashcat_dir
        raise FileNotFoundError("Hashcat directory not configured.")

    def _get_jtr_dir(self) -> Path:
        if self.jtr_dir:
            return self.jtr_dir
        raise FileNotFoundError("John the Ripper not configured. Go to General → Tool Paths.")

    # ── Subprocess Helpers ──

    def _stream_process(
        self,
        cmd: list[str],
        cwd: str | Path,
        on_output: Callable[[str], None],
        on_done: Callable[[], None],
        *,
        creation_flags: int = 0,
        store_proc: bool = False,
    ) -> int:
        """
        Run a subprocess and stream its stdout line-by-line.

        Args:
            creation_flags: Windows process creation flags (e.g. CREATE_NEW_PROCESS_GROUP).
            store_proc: If True, store the process in _active_proc for external control.

        Returns the process exit code.
        All errors are reported via on_output, never raises.
        """
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                errors="replace",
                creationflags=creation_flags | (subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0),
            )

            if store_proc:
                with self._proc_lock:
                    if self._active_proc is not None and self._active_proc.poll() is None:
                        proc.kill()
                        on_output("[!] Another hashcat process is already running.\n")
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
            on_done()

    @staticmethod
    def _run_quiet(cmd: list[str], cwd: str | Path, timeout: int = 15) -> subprocess.CompletedProcess:
        """Run a subprocess quietly and return the result. No streaming."""
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

    # ── Hashcat Process Control ──

    def stop(self) -> None:
        """Kill the active hashcat process immediately. No state is saved."""
        proc = self._active_proc
        if proc is None or proc.poll() is not None:
            return
        try:
            # If paused, resume first so kill takes effect cleanly
            if self._paused:
                psutil.Process(proc.pid).resume()
                self._paused = False
            proc.kill()
            log.info("Hashcat process killed.")
        except Exception as e:
            log.warning("Failed to stop hashcat: %s", e)

    def pause(self) -> bool:
        """Suspend the hashcat process. Returns True if paused successfully."""
        proc = self._active_proc
        if proc is None or proc.poll() is not None or self._paused:
            return False
        try:
            psutil.Process(proc.pid).suspend()
            self._paused = True
            log.info("Hashcat process paused.")
            return True
        except Exception as e:
            log.warning("Failed to pause hashcat: %s", e)
            return False

    def resume(self) -> bool:
        """Resume a paused hashcat process. Returns True if resumed successfully."""
        proc = self._active_proc
        if proc is None or proc.poll() is not None or not self._paused:
            return False
        try:
            psutil.Process(proc.pid).resume()
            self._paused = False
            log.info("Hashcat process resumed.")
            return True
        except Exception as e:
            log.warning("Failed to resume hashcat: %s", e)
            return False

    def checkpoint(self) -> None:
        """
        Send CTRL_BREAK to hashcat for graceful shutdown with state save.
        Hashcat will write a .restore file before exiting.
        Requires --session to be set for restore to work.
        """
        proc = self._active_proc
        if proc is None or proc.poll() is not None:
            return
        try:
            # Resume first if paused
            if self._paused:
                psutil.Process(proc.pid).resume()
                self._paused = False
            if sys.platform == "win32":
                # CTRL_BREAK_EVENT = 1, sent to the process group
                ctypes.windll.kernel32.GenerateConsoleCtrlEvent(1, proc.pid)
            else:
                proc.send_signal(signal.SIGINT)
            log.info("Checkpoint signal sent to hashcat.")
        except Exception as e:
            log.warning("Failed to checkpoint hashcat: %s", e)
            # Fallback: just kill
            try:
                proc.kill()
            except Exception:
                pass

    @property
    def is_running(self) -> bool:
        """Check if a hashcat process is currently active."""
        return self._active_proc is not None and self._active_proc.poll() is None

    @property
    def is_paused(self) -> bool:
        """Check if the active hashcat process is paused."""
        return self._paused

    # ── Hash Extraction ──

    def extract_hash_from_file(self, filepath: str) -> str:
        """
        Try to extract a hash from an encrypted file using *2john tools,
        or via the built-in cap_parser for .cap/.pcap/.pcapng files.
        Returns the extracted hash string or an error message.
        """
        ext = Path(filepath).suffix.lower()

        # ── .cap / .pcap / .pcapng → native Python converter (hc22000) ──
        if ext in CAP_EXTENSIONS:
            return cap_to_hc22000_string(filepath)

        extractor = HASH_EXTRACTORS.get(ext)

        if not extractor:
            supported = ', '.join(sorted(set(HASH_EXTRACTORS) | CAP_EXTENSIONS))
            return f"[!] No extractor for '{ext}' files. Supported: {supported}"

        tool, extra = extractor
        tool_path = self._get_jtr_dir() / tool

        if not tool_path.exists():
            return f"[!] '{tool}' not found in {self._get_jtr_dir()}."

        cmd: list[str] = [str(tool_path)] + extra + [filepath]

        # Windows needs to know how to run .py and .pl files explicitly if associations aren't set
        if tool.endswith(".py"):
            cmd = ["python"] + cmd
        elif tool.endswith(".pl"):
            cmd = ["perl"] + cmd

        log.info("Running: %s", ' '.join(cmd))

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            output = result.stdout.strip()
            if not output and result.stderr.strip():
                return f"[!] {tool} error: {result.stderr.strip()}"
            if not output:
                return f"[!] {tool} returned no output."

            # Parse output safely (some output multiple lines, warnings, etc.)
            lines = output.splitlines()
            extracted = ""
            for line in lines:
                line = line.strip()
                if not line or line.startswith("Warning:") or line.startswith("File "):
                    continue

                # Typical format:  filename.zip:$pkzip2$...:flag.txt...
                if ':$' in line:
                    extracted = '$' + line.split(':$', 1)[1]
                    break
                elif line.startswith('$'):
                    extracted = line
                    break

            if not extracted:
                extracted = output

            # Strip trailing John-specific metadata separated by colons
            if extracted.startswith("$pkzip2$"):
                end_idx = extracted.find("$/pkzip2$")
                if end_idx != -1:
                    extracted = extracted[:end_idx + len("$/pkzip2$")]
            elif extracted.startswith("$zip2$") or extracted.startswith("$rar") or extracted.startswith("$7z$") or extracted.startswith("$pdf$") or extracted.startswith("$office$"):
                extracted = extracted.split(":")[0]

            return extracted.strip()
        except FileNotFoundError:
            return f"[!] '{tool}' not found. Install John the Ripper and ensure it's in PATH."
        except subprocess.TimeoutExpired:
            return f"[!] '{tool}' timed out."
        except Exception as e:
            return f"[!] Extraction failed: {e}"

    # ── Hashcat Operations ──

    def _hashcat_show(self, m_value: str) -> str | None:
        """Run hashcat --show to check if hash is already cracked. Returns password or None."""
        try:
            result = self._run_quiet(
                [str(self._get_hashcat_exe()), "-m", m_value, "--show", str(TARGET_HASH_FILE)],
                cwd=self._get_hashcat_cwd(),
            )
            output = result.stdout.strip()
            if output:
                # Format: hash:password  or  hash_fields:password (last colon-separated field)
                last_line = output.splitlines()[-1]
                password = last_line.rsplit(":", 1)[-1]
                if password:
                    return password
        except Exception:
            pass
        return None

    def _build_hashcat_cmd(
        self,
        m_value: str,
        settings: dict[str, Any],
    ) -> list[str]:
        """Build the full hashcat command from settings dict."""
        cmd = [str(self._get_hashcat_exe())]

        a_mode = settings.get("attack_mode", "0")
        cmd += ["-a", a_mode, "-m", m_value]

        cmd += ["-d", settings.get("device", "1")]
        cmd += ["-w", settings.get("workload_profile", "2")]

        # Live status updates for progress bar
        cmd += ["--status", "--status-timer=2"]

        if settings.get("optimized_kernel"):
            cmd.append("-O")

        if settings.get("session_name"):
            cmd += ["--session", settings["session_name"]]

        if settings.get("hwmon_temp_abort"):
            cmd += ["--hwmon-temp-abort", settings["hwmon_temp_abort"]]

        for i in range(1, 5):
            cs = settings.get(f"custom_charset_{i}")
            if cs:
                cmd += [f"-{i}", cs]

        if settings.get("disable_potfile"):
            cmd.append("--potfile-disable")

        if settings.get("skip"):
            cmd += ["-s", settings["skip"]]

        if settings.get("limit"):
            cmd += ["--limit", settings["limit"]]

        # Hash file (direct path or temp file)
        hash_file = settings.get("hash_file_path") or str(TARGET_HASH_FILE)
        cmd.append(hash_file)

        # Attack payload: depends on mode
        # Mode 0: wordlist [+ rules]
        # Mode 1: wordlist (combinator - needs 2 wordlists, we use one)
        # Mode 3: mask only
        # Mode 6: wordlist + mask (hybrid)
        # Mode 7: mask + wordlist (hybrid)
        if a_mode == "3":
            if settings.get("mask"):
                cmd.append(settings["mask"])
        elif a_mode in ("6", "7"):
            # Hybrid: need both wordlist and mask
            if a_mode == "6":
                # wordlist first, then mask
                if settings.get("wordlist"):
                    cmd.append(settings["wordlist"])
                if settings.get("mask"):
                    cmd.append(settings["mask"])
            else:  # mode 7
                # mask first, then wordlist
                if settings.get("mask"):
                    cmd.append(settings["mask"])
                if settings.get("wordlist"):
                    cmd.append(settings["wordlist"])
        else:
            # Mode 0, 1: wordlist + optional rules
            if settings.get("wordlist"):
                cmd.append(settings["wordlist"])
            # Multi-rule stacking: each rule gets its own -r flag
            rules = settings.get("rules", [])
            if rules:
                for r in rules:
                    cmd += ["-r", r]
            elif settings.get("rule"):
                # Backward compat: single rule
                cmd += ["-r", settings["rule"]]

        return cmd

    def run_crack(
        self,
        hash_value: str,
        m_value: str,
        settings: dict,
        on_output: Callable[[str], None],
        on_done: Callable[[], None],
    ) -> None:
        """
        Executes Hashcat in a subprocess and streams output.
        This should be run in a separate thread to not block the main loop.
        """
        # Write hash to temp file (unless a hash file path is provided)
        hash_file_path = settings.get("hash_file_path")
        if not hash_file_path:
            try:
                TARGET_HASH_FILE.write_text(hash_value, encoding="utf-8")
            except OSError as e:
                on_output(f"[!] Failed to write hash file: {e}\n")
                on_done()
                return

        # ── Check potfile first ──
        if not settings.get("disable_potfile") and not hash_file_path:
            existing_pw = self._hashcat_show(m_value)
            if existing_pw:
                on_output("─" * 60 + "\n")
                on_output(f"[+] Password already cracked (from potfile)!\n\n")
                on_output(f"    ✅  PASSWORD:  {existing_pw}\n\n")
                on_output("─" * 60 + "\n")
                on_output("[*] Use 'Disable Potfile' in Advanced tab to re-crack.\n")
                on_done()
                return

        # Build command
        cmd = self._build_hashcat_cmd(m_value, settings)

        on_output("─" * 60 + "\n")

        # Use CREATE_NEW_PROCESS_GROUP on Windows so we can send CTRL_BREAK for checkpoint
        cflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0

        rc = self._stream_process(
            cmd, cwd=self._get_hashcat_cwd(), on_output=on_output, on_done=lambda: None,
            creation_flags=cflags, store_proc=True,
        )

        on_output(f"\n{'─' * 60}\n")

        # ── After crack: check result ──
        cracked_pw = self._hashcat_show(m_value)
        if cracked_pw:
            on_output(f"\n    ✅  PASSWORD FOUND:  {cracked_pw}\n\n")
        elif rc == 1:
            on_output(f"\n    ❌  EXHAUSTED — Password not found in wordlist/mask.\n\n")
        elif rc == 0:
            on_output("[+] Hashcat finished successfully.\n")
        else:
            on_output(f"[*] Hashcat exited with code {rc}.\n")

        on_done()

    def get_devices(self) -> list[tuple[str, str]]:
        """Returns a list of (device_id, device_name) from Hashcat."""
        devices = []
        try:
            result = self._run_quiet([str(self._get_hashcat_exe()), "-I"], cwd=self._get_hashcat_cwd(), timeout=30)

            current_id = None
            for line in result.stdout.splitlines():
                id_match = re.search(r'Backend Device ID #(\d+)', line)
                if id_match:
                    current_id = str(int(id_match.group(1)))  # strip leading zeros if any
                    continue

                if current_id and "Name" in line:
                    name_match = re.search(r'Name\.*:\s*(.+)', line)
                    if name_match:
                        name = name_match.group(1).strip()
                        devices.append((current_id, name))
                        current_id = None # wait for next ID

        except Exception as e:
            log.warning("Failed to get devices: %s", e)

        if not devices:
            devices.append(("1", "Default (No devices found)"))

        return devices

    def run_benchmark(self, device_id: str, on_output: Callable[[str], None], on_done: Callable[[], None]) -> None:
        """Run a quick benchmark on MD5 (m=0) and NTLM (m=1000) for the given device."""
        cmd = [str(self._get_hashcat_exe()), "-b", "-m", "0", "-m", "1000", "-d", device_id]

        on_output(f"[*] Benchmarking Device ID: {device_id}\n")
        on_output("─" * 60 + "\n")

        rc = self._stream_process(cmd, cwd=self._get_hashcat_cwd(), on_output=on_output, on_done=lambda: None)

        on_output(f"\n{'─' * 60}\n")
        if rc == 0:
            on_output("[+] Benchmark finished successfully.\n")
        else:
            on_output(f"[*] Benchmark exited with code {rc}.\n")

        on_done()

    def run_restore(
        self,
        session_name: str,
        on_output: Callable[[str], None],
        on_done: Callable[[], None],
    ) -> None:
        """
        Restore a previously checkpointed hashcat session.
        Hashcat reads all parameters from the .restore file — no extra args needed.
        """
        cmd = [str(self._get_hashcat_exe()), "--session", session_name, "--restore",
               "--status", "--status-timer=2"]

        on_output(f"[*] Restoring session: {session_name}\n")
        on_output("─" * 60 + "\n")

        cflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0

        rc = self._stream_process(
            cmd, cwd=self._get_hashcat_cwd(), on_output=on_output, on_done=lambda: None,
            creation_flags=cflags, store_proc=True,
        )

        on_output(f"\n{'─' * 60}\n")
        if rc == 0:
            on_output("[+] Restored session finished successfully.\n")
        elif rc == 1:
            on_output("\n    ❌  EXHAUSTED — Password not found.\n\n")
        else:
            on_output(f"[*] Hashcat exited with code {rc}.\n")

        on_done()
