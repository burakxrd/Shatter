import logging
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core import TEMP_DIR
from core.process import ManagedProcess

log = logging.getLogger(__name__)

TARGET_HASH_FILE = TEMP_DIR / "target_hash.txt"
SESSIONS_DIR = TEMP_DIR / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

from core.engine_base import BaseEngine

class HashcatEngine(BaseEngine):
    """Manages Hashcat command building and execution using ManagedProcess."""

    def __init__(self, hashcat_exe: Path | None = None, hashcat_dir: Path | None = None) -> None:
        self.hashcat_exe = hashcat_exe
        self.hashcat_dir = hashcat_dir
        self.process = ManagedProcess()
        self._last_session: str | None = None
        self._last_restore_file: Path | None = None

    def _get_hashcat_exe(self) -> Path:
        if self.hashcat_exe:
            return self.hashcat_exe
        raise FileNotFoundError("Hashcat not configured. Go to General → Tool Paths.")

    def _get_hashcat_cwd(self) -> Path:
        if self.hashcat_dir:
            return self.hashcat_dir
        raise FileNotFoundError("Hashcat directory not configured.")

    def stop(self) -> None:
        self.process.stop()

    def pause(self) -> bool:
        return self.process.pause()

    def resume(self) -> bool:
        return self.process.resume()

    def checkpoint(self) -> None:
        self.process.checkpoint()

    @property
    def is_running(self) -> bool:
        return self.process.is_running

    @property
    def is_paused(self) -> bool:
        return self.process.is_paused

    def _hashcat_show(self, m_value: str) -> str | None:
        try:
            result = self.process.run_quiet(
                [str(self._get_hashcat_exe()), "-m", m_value, "--show", str(TARGET_HASH_FILE)],
                cwd=self._get_hashcat_cwd(),
            )
            output = result.stdout.strip()
            if output:
                last_line = output.splitlines()[-1]
                password = last_line.rsplit(":", 1)[-1]
                if password:
                    return password
        except Exception:
            pass
        return None

    def _build_hashcat_cmd(self, m_value: str, settings: dict[str, Any]) -> list[str]:
        from core.sanitizer import validate_cli_arg
        cmd = [str(self._get_hashcat_exe())]
        a_mode = settings.get("attack_mode", "0")
        cmd += ["-a", a_mode, "-m", m_value]
        cmd += ["-d", settings.get("device", "1")]

        workload = settings.get("workload_profile", "2")
        if workload:
            valid, err = validate_cli_arg("workload_profile", workload)
            if valid:
                cmd += ["-w", workload]
            else:
                log.warning("Invalid workload_profile rejected: %s", err)

        cmd += ["--status", "--status-timer=2"]

        if settings.get("optimized_kernel"):
            cmd.append("-O")
        
        session = settings.get("session_name")
        if session:
            valid, err = validate_cli_arg("session_name", session)
            if valid:
                DEFAULT_SESSION = "shatter"

                # Always wipe ALL existing restore files for this session name from
                # SESSIONS_DIR and the hashcat CWD so hashcat doesn't see a stale
                # session and exit with code 4294967295 ("Session already exists").
                for existing in SESSIONS_DIR.glob(f"{session}*.restore"):
                    try:
                        existing.unlink()
                    except Exception:
                        pass
                old_cwd_restore = self._get_hashcat_cwd() / f"{session}.restore"
                if old_cwd_restore.exists():
                    try:
                        old_cwd_restore.unlink()
                    except Exception:
                        pass

                # Now pick the save path.
                # For the default name ("shatter") keep a numbered history so previous
                # sessions aren't lost — the NEW file will be written by hashcat during
                # this run and we use the first free slot (shatter.restore,
                # shatter1.restore, …) as the target path.
                if session == DEFAULT_SESSION:
                    restore_file = SESSIONS_DIR / f"{session}.restore"
                    counter = 1
                    # After the glob-delete above the dir should be clean; this guard
                    # is a safety net in case something else created a file in between.
                    while restore_file.exists():
                        restore_file = SESSIONS_DIR / f"{session}{counter}.restore"
                        counter += 1
                else:
                    restore_file = SESSIONS_DIR / f"{session}.restore"

                cmd += ["--session", session]
                cmd += ["--restore-file-path", str(restore_file)]
                # Track for checkpoint/UI feedback
                self._last_session = session
                self._last_restore_file = restore_file
            else:
                log.warning("Invalid session_name rejected: %s", err)

        if settings.get("hwmon_temp_abort"):
            cmd += ["--hwmon-temp-abort", settings["hwmon_temp_abort"]]

        for i in range(1, 5):
            cs = settings.get(f"custom_charset_{i}")
            if cs:
                cmd += [f"-{i}", cs]

        if settings.get("disable_potfile"):
            cmd.append("--potfile-disable")
        if settings.get("disable_self_test"):
            cmd.append("--self-test-disable")
        if settings.get("skip"):
            cmd += ["-s", settings["skip"]]
        if settings.get("limit"):
            cmd += ["--limit", settings["limit"]]

        hash_file = settings.get("hash_file_path") or str(TARGET_HASH_FILE)
        cmd.append(hash_file)

        mask = settings.get("mask")
        if mask:
            valid, err = validate_cli_arg("mask", mask)
            if not valid:
                log.warning("Invalid mask rejected: %s", err)
                mask = None

        if a_mode == "3":
            if mask:
                cmd.append(mask)
        elif a_mode in ("6", "7"):
            if a_mode == "6":
                if settings.get("wordlist"):
                    cmd.append(settings["wordlist"])
                if mask:
                    cmd.append(mask)
            else:
                if mask:
                    cmd.append(mask)
                if settings.get("wordlist"):
                    cmd.append(settings["wordlist"])
        else:
            if settings.get("wordlist"):
                cmd.append(settings["wordlist"])
            rules = settings.get("rules", [])
            if rules:
                for r in rules:
                    cmd += ["-r", r]
            elif settings.get("rule"):
                cmd += ["-r", settings["rule"]]

        return cmd

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _run_hashcat(
        self,
        cmd: list[str],
        on_output: Callable[[str], None],
        session_name: str | None = None,
        restore_file: "Path | None" = None,
    ) -> int:
        """Stream a hashcat command, track session info, and return the exit code.

        This is the single place where:
        - _last_session / _last_restore_file are updated (for checkpoint feedback)
        - creation_flags are set (CREATE_NEW_PROCESS_GROUP for CTRL_BREAK)
        - stream_process is called
        """
        if session_name:
            self._last_session = session_name
        if restore_file:
            self._last_restore_file = restore_file

        cflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        return self.process.stream_process(
            cmd,
            cwd=self._get_hashcat_cwd(),
            on_output=on_output,
            on_done=lambda: None,
            creation_flags=cflags,
            store_proc=True,
        )

    @staticmethod
    def _hashcat_exit_message(rc: int) -> str | None:
        """Return a human-readable summary for a hashcat exit code, or None for rc==0."""
        if rc == 1:
            return "\n    \u274c  EXHAUSTED \u2014 Password not found in wordlist/mask.\n\n"
        if rc == 2:
            return "[*] Hashcat aborted (checkpoint or quit).\n"
        if rc == 0:
            return None  # handled by the caller (cracked / finished)
        return f"[*] Hashcat exited with code {rc}.\n"

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def run_crack(
        self,
        hash_value: str,
        m_value: str,
        settings: dict,
        on_output: Callable[[str], None],
        on_done: Callable[[], None],
    ) -> None:
        hash_file_path = settings.get("hash_file_path")
        if not hash_file_path:
            try:
                TARGET_HASH_FILE.write_text(hash_value, encoding="utf-8")
            except OSError as e:
                on_output(f"[!] Failed to write hash file: {e}\n")
                on_done()
                return

        if not settings.get("disable_potfile") and not hash_file_path:
            existing_pw = self._hashcat_show(m_value)
            if existing_pw:
                on_output("\u2500" * 60 + "\n")
                on_output("[+] Password already cracked (from potfile)!\n\n")
                on_output(f"    \u2705  PASSWORD:  {existing_pw}\n\n")
                on_output("\u2500" * 60 + "\n")
                on_output("[*] Use 'Disable Potfile' in Advanced tab to re-crack.\n")
                on_done()
                return

        cmd = self._build_hashcat_cmd(m_value, settings)
        on_output("\u2500" * 60 + "\n")

        # Capture cracked password from stdout (HASH:PASSWORD line).
        # Works whether potfile is enabled or not.
        _captured_pw: str | None = None

        def _capturing_output(line: str) -> None:
            nonlocal _captured_pw
            on_output(line)
            if _captured_pw is not None:
                return
            stripped = line.strip()
            if not stripped or stripped.startswith(("[", "*", "#", "-", "=")):
                return
            target = hash_value.strip() if not hash_file_path else None
            if target and stripped.startswith(target) and ":" in stripped[len(target):]:
                _captured_pw = stripped[len(target) + 1:]

        # Pull session info from the command we just built
        session_name = self._last_session
        restore_file = self._last_restore_file
        rc = self._run_hashcat(cmd, _capturing_output, session_name, restore_file)

        on_output(f"\n{'\u2500' * 60}\n")
        cracked_pw = _captured_pw or (
            self._hashcat_show(m_value) if not settings.get("disable_potfile") else None
        )
        if cracked_pw:
            on_output(f"\n    \u2705  PASSWORD FOUND:  {cracked_pw}\n\n")
        elif msg := self._hashcat_exit_message(rc):
            on_output(msg)
        else:
            on_output("[+] Hashcat finished successfully.\n")

        on_done()

    def get_devices(self) -> list[tuple[str, str]]:
        import re
        devices = []
        try:
            result = self.process.run_quiet([str(self._get_hashcat_exe()), "-I"], cwd=self._get_hashcat_cwd(), timeout=30)
            current_id = None
            for line in result.stdout.splitlines():
                id_match = re.search(r'Backend Device ID #(\d+)', line)
                if id_match:
                    current_id = str(int(id_match.group(1)))
                    continue

                if current_id and "Name" in line:
                    name_match = re.search(r'Name\.*:\s*(.+)', line)
                    if name_match:
                        name = name_match.group(1).strip()
                        devices.append((current_id, name))
                        current_id = None
        except Exception as e:
            log.warning("Failed to get devices: %s", e)

        if not devices:
            devices.append(("1", "Default (No devices found)"))
        return devices

    def run_benchmark(self, device_id: str, on_output: Callable[[str], None], on_done: Callable[[], None]) -> None:
        cmd = [str(self._get_hashcat_exe()), "-b", "-d", device_id]
        on_output(f"[*] Benchmarking Device ID: {device_id}\n")
        on_output("─" * 60 + "\n")
        
        rc = self.process.stream_process(cmd, cwd=self._get_hashcat_cwd(), on_output=on_output, on_done=lambda: None)
        
        on_output(f"\n{'─' * 60}\n")
        if rc == 0:
            on_output("[+] Benchmark finished successfully.\n")
        else:
            on_output(f"[*] Benchmark exited with code {rc}.\n")
        on_done()

    def run_restore(
        self,
        session_name: str,
        restore_file_path: str,
        on_output: Callable[[str], None],
        on_done: Callable[[], None],
    ) -> None:
        from core.sanitizer import validate_cli_arg
        valid, err = validate_cli_arg("session_name", session_name)
        if not valid:
            on_output(f"[!] Invalid session_name: {err}\n")
            on_done()
            return

        cmd = [
            str(self._get_hashcat_exe()),
            "--session", session_name,
            "--restore",
            "--restore-file-path", restore_file_path,
            "--status", "--status-timer=2",
        ]

        on_output(f"[*] Restoring session: {session_name}\n")
        on_output(f"[*] Restore file: {restore_file_path}\n")
        on_output("\u2500" * 60 + "\n")

        rc = self._run_hashcat(cmd, on_output, session_name, Path(restore_file_path))

        on_output(f"\n{'\u2500' * 60}\n")
        if rc == 0:
            on_output("[+] Restored session finished successfully.\n")
        elif msg := self._hashcat_exit_message(rc):
            on_output(msg)

        on_done()
