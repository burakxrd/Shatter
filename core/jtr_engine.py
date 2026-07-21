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

from core.engine_base import BaseEngine

class JtrEngine(BaseEngine):
    """Manages John the Ripper command building and execution using ManagedProcess."""

    def __init__(self, jtr_dir: Path | None = None) -> None:
        self.jtr_dir = jtr_dir
        self.process = ManagedProcess()

    def _get_jtr_exe(self) -> Path:
        if self.jtr_dir:
            exe = self.jtr_dir / "john.exe"
            if exe.exists():
                return exe
        raise FileNotFoundError("John the Ripper not configured. Go to General → Tool Paths.")

    def _get_jtr_cwd(self) -> Path:
        if self.jtr_dir:
            return self.jtr_dir
        raise FileNotFoundError("JtR directory not configured.")

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

    def _jtr_show(self, format_name: str | None = None) -> str | None:
        try:
            cmd = [str(self._get_jtr_exe()), "--show", str(TARGET_HASH_FILE)]
            if format_name:
                cmd.insert(1, f"--format={format_name}")
                
            result = self.process.run_quiet(cmd, cwd=self._get_jtr_cwd())
            output = result.stdout.strip()
            
            # Look for lines indicating cracked passwords
            # E.g. "password123      (admin)"
            for line in output.splitlines():
                if " (" in line and line.endswith(")"):
                    return line.split(" (", 1)[0].strip()
                    
        except Exception:
            pass
        return None

    def _build_jtr_cmd(self, jtr_format: str | None, settings: dict[str, Any]) -> list[str]:
        from core.sanitizer import validate_cli_arg
        cmd = [str(self._get_jtr_exe())]
        
        if jtr_format:
            # Sadece alfanumerik ve tire/altçizgi
            import re
            if re.match(r'^[a-zA-Z0-9_\-]+$', jtr_format):
                cmd.append(f"--format={jtr_format}")
            else:
                log.warning("Invalid jtr_format rejected: %s", jtr_format)
            
        # JtR uses --wordlist for dictionary attacks
        if settings.get("wordlist"):
            cmd.append(f"--wordlist={settings['wordlist']}")
            
        # Add a status timer so we get regular output for progress bar
        cmd.append("--status-timer=2")
            
        hash_file = settings.get("hash_file_path") or str(TARGET_HASH_FILE)
        cmd.append(hash_file)

        return cmd

    def run_crack(
        self,
        hash_value: str,
        jtr_format: str | None,
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

        # Check potfile
        if not settings.get("disable_potfile") and not hash_file_path:
            existing_pw = self._jtr_show(jtr_format)
            if existing_pw:
                on_output("─" * 60 + "\n")
                on_output(f"[+] Password already cracked (from JtR potfile)!\n\n")
                on_output(f"    ✅  PASSWORD:  {existing_pw}\n\n")
                on_output("─" * 60 + "\n")
                on_done()
                return

        cmd = self._build_jtr_cmd(jtr_format, settings)
        on_output("─" * 60 + "\n")
        
        cflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0

        rc = self.process.stream_process(
            cmd, cwd=self._get_jtr_cwd(), on_output=on_output, on_done=lambda: None,
            creation_flags=cflags, store_proc=True,
        )

        on_output(f"\n{'─' * 60}\n")
        cracked_pw = self._jtr_show(jtr_format)
        if cracked_pw:
            on_output(f"\n    ✅  PASSWORD FOUND:  {cracked_pw}\n\n")
        elif rc != 0:
            on_output(f"[*] John the Ripper exited with code {rc}.\n")
        else:
            on_output("[+] John the Ripper finished successfully.\n")

        on_done()
