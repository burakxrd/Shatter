"""handlers.py — All event/action handlers for ShatterApp (Mixin)."""

import re
import threading
from tkinter import filedialog

from core.detector import detect_hash_type, extract_m_value
from core.engine import (
    extract_hash_from_file, run_hashcat, run_hashcat_restore,
    run_benchmark, get_devices, HASH_EXTRACTORS, CAP_EXTENSIONS,
    hashcat_stop, hashcat_pause, hashcat_resume,
    hashcat_checkpoint, is_hashcat_paused,
)
from ui.theme import COLOR_TEXT, COLOR_TEXT_DIM

# Regex for parsing hashcat --status output
_RE_PROGRESS = re.compile(r"Progress\.+:\s*\d+/\d+\s*\((\d+(?:\.\d+)?)%\)")
_RE_ETA = re.compile(r"Time\.Estimated\.+:\s*.+?\(([^)]+)\)")


def _select_file(title: str, filetypes=None) -> str:
    if filetypes is None:
        filetypes = [("All files", "*.*")]
    return filedialog.askopenfilename(title=title, filetypes=filetypes)


class HandlersMixin:
    """Mixin that adds all event handlers to ShatterApp."""

    # ── Attack Mode ──

    def _on_attack_mode_change(self, choice=None) -> None:
        self._update_attack_payload_ui()
        self._save_config()

    # ── Hash Detection (debounced) ──

    def _on_hash_changed(self, _event=None) -> None:
        if self._hash_debounce_id is not None:
            self.after_cancel(self._hash_debounce_id)
        self._hash_debounce_id = self.after(300, self._do_hash_detect)

    def _do_hash_detect(self) -> None:
        self._hash_debounce_id = None
        value = self._hash_entry.get().strip()
        if value:
            algo = detect_hash_type(value)
            self._algo_label.configure(
                text=f"Detected:  {algo}",
                text_color="#4ADE80" if algo != "Unknown / Custom" else "#FF6B6B",
            )
        else:
            self._algo_label.configure(text="Detected Algorithm:  None", text_color=COLOR_TEXT_DIM)
        self._save_config()

    # ── Hash Extraction (from encrypted files) ──

    def _on_extract_hash(self) -> None:
        all_exts = set(HASH_EXTRACTORS) | CAP_EXTENSIONS
        supported = " ".join(f"*{ext}" for ext in sorted(all_exts))
        path = _select_file(
            title="Select Encrypted File",
            filetypes=[("Capture files", "*.cap *.pcap *.pcapng"), ("Supported", supported), ("All", "*.*")],
        )
        if not path:
            return
        self._term_clear()
        self._term_append(f"[*] Extracting hash from: {path}\n")

        def _run():
            result = extract_hash_from_file(path)
            self.after(0, self._finish_extraction, result)

        threading.Thread(target=_run, daemon=True).start()

    def _finish_extraction(self, result: str) -> None:
        if result.startswith("[!]"):
            self._term_append(f"{result}\n")
        else:
            self._hash_entry.delete(0, "end")
            self._hash_entry.insert(0, result)
            self._on_hash_changed()
            self._term_append(f"[+] Hash extracted!\n    {result[:120]}{'…' if len(result) > 120 else ''}\n")

    # ── Hash File Loading ──

    def _on_load_hash_file(self) -> None:
        path = _select_file(title="Select Hash File (.txt)", filetypes=[("Text files", "*.txt"), ("All", "*.*")])
        if not path:
            return
        self._hash_file_path = path
        display = path if len(path) <= 50 else f"…{path[-48:]}"
        self._hashfile_label.configure(text=f"📋 Hash File: {display}")
        self._term_clear()
        # Count lines
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                count = sum(1 for line in f if line.strip())
            self._term_append(f"[+] Hash file loaded: {count} hash(es)\n    {path}\n")
        except Exception as e:
            self._term_append(f"[!] Failed to read hash file: {e}\n")
        self._save_config()

    # ── File Selection ──

    def _on_select_wordlist(self) -> None:
        path = _select_file(title="Select Wordlist File")
        if path:
            self._wordlist_path = path
            display = path if len(path) <= 52 else f"…{path[-50:]}"
            self._wl_path_label.configure(text=display, text_color=COLOR_TEXT)
            self._save_config()

    def _on_add_rule(self) -> None:
        path = _select_file(title="Select Rule File", filetypes=[("Rule files", "*.rule *.rules"), ("All", "*.*")])
        if path and path not in self._rule_paths:
            self._rule_paths.append(path)
            self._update_rule_label()
            self._save_config()

    def _on_clear_rules(self) -> None:
        self._rule_paths.clear()
        self._update_rule_label()
        self._save_config()

    def _update_rule_label(self) -> None:
        if not self._rule_paths:
            self._rule_path_label.configure(text="No rules", text_color=COLOR_TEXT_DIM)
        else:
            from pathlib import Path
            names = [Path(p).name for p in self._rule_paths]
            self._rule_path_label.configure(text=" + ".join(names), text_color=COLOR_TEXT)

    # ── Progress Parsing ──

    def _parse_and_update_progress(self, text: str) -> None:
        """Parse hashcat status output and update progress bar / ETA label."""
        m_prog = _RE_PROGRESS.search(text)
        if m_prog:
            pct = float(m_prog.group(1))
            self._progress_bar.set(pct / 100.0)
            eta_str = ""
            m_eta = _RE_ETA.search(text)
            if m_eta:
                eta_str = f"  ETA: {m_eta.group(1)}"
            self._eta_label.configure(text=f"{pct:.1f}%{eta_str}")

    # ── CRACK ──

    def _on_crack(self) -> None:
        self._flush_save()

        hash_value = self._hash_entry.get().strip()
        mode = self._attack_mode_var.get()
        needs_mask = mode[0] in ("3", "6", "7")
        needs_wordlist = mode[0] in ("0", "1", "6", "7")

        if not hash_value and not self._hash_file_path:
            self._term_clear()
            self._term_append("[!] Error: No hash provided.\n")
            return
        if needs_mask and not self._mask_entry.get().strip():
            self._term_clear()
            self._term_append("[!] Error: No mask provided.\n")
            return
        if needs_wordlist and not self._wordlist_path:
            self._term_clear()
            self._term_append("[!] Error: No wordlist selected.\n")
            return

        # Determine hash mode
        if hash_value:
            algo_str = detect_hash_type(hash_value)
            m_value = extract_m_value(algo_str)
        else:
            m_value = None

        if not m_value:
            self._term_clear()
            self._term_append("[!] Could not determine Hashcat mode (-m).\n")
            self._term_append("[*] Hash file modunda ilk hash'i entry'ye yapıştırarak mode belirleyin.\n")
            return

        self._crack_button.configure(state="disabled", text="⏳  Running…")
        self._restore_button.configure(state="disabled")
        self._bench_button.configure(state="disabled")
        self._term_clear()
        self._progress_bar.set(0)
        self._eta_label.configure(text="0%")

        device_id = self._device_map.get(self._device_var.get(), "1")
        self._term_append(f"[*] Mode: -m {m_value}  |  Device: {device_id}\n")

        settings = {
            "device": device_id,
            "attack_mode": mode[0],
            "workload_profile": self._workload_var.get()[0],
            "optimized_kernel": self._opt_kernel_var.get(),
            "session_name": self._session_var.get().strip(),
            "hwmon_temp_abort": self._temp_abort_var.get().strip(),
            "custom_charset_1": self._charset1_var.get().strip(),
            "custom_charset_2": self._charset2_var.get().strip(),
            "custom_charset_3": self._charset3_var.get().strip(),
            "custom_charset_4": self._charset4_var.get().strip(),
            "disable_potfile": self._disable_potfile_var.get(),
            "skip": self._skip_var.get().strip(),
            "limit": self._limit_var.get().strip(),
            "wordlist": self._wordlist_path,
            "mask": self._mask_entry.get().strip(),
            "rules": self._rule_paths,
            "hash_file_path": self._hash_file_path,
        }

        def _on_output(text):
            self.after(0, self._term_append, text)
            self.after(0, self._parse_and_update_progress, text)

        def _on_done():
            self.after(0, self._crack_done)

        threading.Thread(target=run_hashcat, args=(hash_value, m_value, settings, _on_output, _on_done), daemon=True).start()
        self._control_frame.grid()

    def _crack_done(self) -> None:
        self._crack_button.configure(state="normal", text="⚡  CRACK")
        self._restore_button.configure(state="normal")
        self._bench_button.configure(state="normal")
        self._control_frame.grid_remove()
        self._pause_button.configure(text="⏸  Mola", fg_color="#FD7E14", hover_color="#D36B0B")

    # ── RESTORE ──

    def _on_restore(self) -> None:
        session = self._session_var.get().strip()
        if not session:
            self._term_clear()
            self._term_append("[!] Error: Session name boş. General sekmesinden bir isim girin.\n")
            return

        self._crack_button.configure(state="disabled")
        self._restore_button.configure(state="disabled", text="⏳ Restoring…")
        self._bench_button.configure(state="disabled")
        self._term_clear()
        self._progress_bar.set(0)
        self._eta_label.configure(text="Restoring…")

        def _on_output(text):
            self.after(0, self._term_append, text)
            self.after(0, self._parse_and_update_progress, text)

        def _on_done():
            self.after(0, self._restore_done)

        threading.Thread(target=run_hashcat_restore, args=(session, _on_output, _on_done), daemon=True).start()
        self._control_frame.grid()

    def _restore_done(self) -> None:
        self._crack_button.configure(state="normal")
        self._restore_button.configure(state="normal", text="🔄 RESTORE")
        self._bench_button.configure(state="normal")
        self._control_frame.grid_remove()
        self._pause_button.configure(text="⏸  Mola", fg_color="#FD7E14", hover_color="#D36B0B")

    # ── BENCHMARK ──

    def _on_benchmark(self) -> None:
        device_id = self._device_map.get(self._device_var.get(), "1")
        self._crack_button.configure(state="disabled")
        self._bench_button.configure(state="disabled", text="⏳ Testing…")
        self._term_clear()

        def _on_output(text):
            self.after(0, self._term_append, text)

        def _on_done():
            self.after(0, self._bench_done)

        threading.Thread(target=run_benchmark, args=(device_id, _on_output, _on_done), daemon=True).start()

    def _bench_done(self) -> None:
        self._crack_button.configure(state="normal")
        self._bench_button.configure(state="normal", text="⏱️ Speed Test")

    # ── Process Control ──

    def _on_stop(self) -> None:
        hashcat_stop()
        self._term_append("\n[!] Hashcat durduruldu (kill).\n")

    def _on_pause_toggle(self) -> None:
        if is_hashcat_paused():
            if hashcat_resume():
                self._pause_button.configure(text="⏸  Mola", fg_color="#FD7E14", hover_color="#D36B0B")
                self._term_append("[*] Hashcat devam ediyor...\n")
        else:
            if hashcat_pause():
                self._pause_button.configure(text="▶  Devam", fg_color="#198754", hover_color="#146C43")
                self._term_append("[*] Hashcat duraklatıldı (mola).\n")

    def _on_checkpoint(self) -> None:
        session = self._session_var.get().strip()
        hashcat_checkpoint()
        if session:
            self._term_append(f"\n[*] Checkpoint (session: {session})…\n")
        else:
            self._term_append("\n[!] Session adı yok — restore dosyası oluşmayabilir.\n")
