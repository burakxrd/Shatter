"""
Shatter — Advanced Hash Cracker
Main application: window, config, terminal, entry point.
"""

import json
import logging
from pathlib import Path

from tkinterdnd2 import TkinterDnD, DND_FILES
import customtkinter as ctk

from core.log_config import setup_logging
from ui.theme import (
    APP_TITLE, APP_GEOMETRY, APP_MIN_SIZE,
    FONT_TERMINAL, COLOR_TERM_BG, COLOR_TERM_FG,
    FONT_TITLE, FONT_SUBTITLE, FONT_PATH,
    COLOR_ACCENT, COLOR_BG_DARK, COLOR_BG_CARD, COLOR_TEXT_DIM,
)
from core.engine import get_devices, hashcat_stop
from core import tool_paths, TEMP_DIR
from ui.dashboard import DashboardMixin
from ui.settings import SettingsMixin
from ui.potfile import PotfileMixin
from ui.handlers import HandlersMixin

CONFIG_FILE = TEMP_DIR / "config.json"
log = logging.getLogger(__name__)


class TkDndWrapper(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)

class ShatterApp(DashboardMixin, SettingsMixin, PotfileMixin, HandlersMixin, TkDndWrapper):
    """Main application — assembled from mixins."""

    def __init__(self) -> None:
        super().__init__()

        self.title(APP_TITLE)
        self.geometry(APP_GEOMETRY)
        self.minsize(*APP_MIN_SIZE)
        self.configure(fg_color=COLOR_BG_DARK)

        # ── State ──
        self._wordlist_path: str | None = None
        self._rule_paths: list[str] = []
        self._hash_file_path: str | None = None

        # ── Tool paths (resolve before anything else) ──
        self._tool_config = self._early_load_tool_paths()

        self._device_list = get_devices()
        self._device_map = {f"#{d_id}: {name}": d_id for d_id, name in self._device_list}
        self._device_var = ctk.StringVar()

        self._attack_mode_var = ctk.StringVar(value="0 (Wordlist)")
        self._workload_var = ctk.StringVar(value="3 (High)")
        self._opt_kernel_var = ctk.BooleanVar(value=True)
        self._session_var = ctk.StringVar(value="")
        self._temp_abort_var = ctk.StringVar(value="90")
        self._charset1_var = ctk.StringVar(value="")
        self._charset2_var = ctk.StringVar(value="")
        self._charset3_var = ctk.StringVar(value="")
        self._charset4_var = ctk.StringVar(value="")
        self._disable_potfile_var = ctk.BooleanVar(value=False)
        self._skip_var = ctk.StringVar(value="")
        self._limit_var = ctk.StringVar(value="")

        # Tool path StringVars (for UI)
        self._hc_path_var = ctk.StringVar(value=str(tool_paths.hashcat_dir or ""))
        self._jtr_path_var = ctk.StringVar(value=str(tool_paths.jtr_dir or ""))

        # ── Debounce timers ──
        self._hash_debounce_id: str | None = None
        self._save_debounce_id: str | None = None

        # ── Build UI ──
        self._build_ui()
        self._load_config()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Show setup hint if hashcat not found
        if not tool_paths.hashcat_exe:
            self.after(500, self._show_setup_hint)

        # Setup Drag and Drop
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self._on_file_drop)

    def _early_load_tool_paths(self) -> dict:
        """Load config.json just for tool paths, configure tool_paths module."""
        config = {}
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    import json as _json
                    config = _json.load(f)
            except Exception:
                pass
        return tool_paths.configure(config)

    def _show_setup_hint(self) -> None:
        self._term_append("⚠️  Hashcat not found!\n")
        self._term_append("   Select hashcat folder from 'Tool Paths' in the General tab.\n")
        self._tabview.set("General")

    # ──────────────────────────────────────────
    #  UI Assembly
    # ──────────────────────────────────────────

    def _build_ui(self) -> None:
        c = ctk.CTkFrame(self, fg_color=COLOR_BG_CARD, corner_radius=16)
        c.pack(fill="both", expand=True, padx=20, pady=20)
        c.grid_columnconfigure(0, weight=1)
        c.grid_rowconfigure(2, weight=1)

        # Header
        hdr = ctk.CTkFrame(c, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 0))
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="⚡  Shatter", font=FONT_TITLE, text_color=COLOR_ACCENT).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hdr, text="Advanced Hash Cracker", font=FONT_SUBTITLE, text_color=COLOR_TEXT_DIM).grid(row=1, column=0, sticky="w")
        ctk.CTkButton(hdr, text="🗑️ Clear", font=FONT_PATH, fg_color="transparent",
            text_color=COLOR_TEXT_DIM, hover_color="#2D2D3F", width=80, height=24,
            command=self._clear_config).grid(row=0, column=1, rowspan=2, sticky="e")

        # Tabs
        tv = ctk.CTkTabview(c, fg_color=COLOR_BG_DARK, corner_radius=10)
        tv.grid(row=1, column=0, sticky="nsew", padx=16, pady=(8, 16))
        self._tabview = tv

        self._build_dashboard(tv.add("Dashboard"))
        self._build_general(tv.add("General"))
        self._build_advanced(tv.add("Advanced"))
        self._build_potfile(tv.add("Potfile"))

        # Auto-refresh potfile when switching to that tab
        tv.configure(command=self._on_tab_change)

        # Terminal / Event Log
        ctk.CTkLabel(c, text="Event Log", font=("Segoe UI", 13, "bold"),
            text_color=COLOR_TEXT_DIM, anchor="w").grid(row=2, column=0, padx=20, sticky="sw", pady=(0, 2))
        self._terminal = ctk.CTkTextbox(c, font=FONT_TERMINAL, fg_color=COLOR_TERM_BG,
            text_color=COLOR_TERM_FG, corner_radius=10, border_width=1,
            border_color="#334155", height=150, state="disabled")
        self._terminal.grid(row=3, column=0, padx=16, sticky="nsew", pady=(0, 16))

    # ──────────────────────────────────────────
    #  Terminal Helpers
    # ──────────────────────────────────────────

    def _term_append(self, text: str) -> None:
        self._terminal.configure(state="normal")
        self._terminal.insert("end", text)
        self._terminal.see("end")
        self._terminal.configure(state="disabled")

    def _term_clear(self) -> None:
        self._terminal.configure(state="normal")
        self._terminal.delete("1.0", "end")
        self._terminal.configure(state="disabled")

    def _on_tab_change(self) -> None:
        """Auto-refresh potfile when switching to Potfile tab."""
        if self._tabview.get() == "Potfile":
            self._potfile_refresh()

    # ──────────────────────────────────────────
    #  Config Persistence
    # ──────────────────────────────────────────

    def _save_config(self) -> None:
        if self._save_debounce_id is not None:
            self.after_cancel(self._save_debounce_id)
        self._save_debounce_id = self.after(500, self._do_save_config)

    def _do_save_config(self) -> None:
        self._save_debounce_id = None
        try:
            data = {
                "hash": self._hash_entry.get().strip(),
                "wordlist": self._wordlist_path,
                "rules": self._rule_paths,
                "hash_file_path": self._hash_file_path,
                "mask": self._mask_entry.get().strip(),
                "device": self._device_map.get(self._device_var.get(), "1"),
                "attack_mode": self._attack_mode_var.get(),
                "workload_profile": self._workload_var.get(),
                "optimized_kernel": self._opt_kernel_var.get(),
                "session_name": self._session_var.get().strip(),
                "hwmon_temp_abort": self._temp_abort_var.get().strip(),
                "charset1": self._charset1_var.get().strip(),
                "charset2": self._charset2_var.get().strip(),
                "charset3": self._charset3_var.get().strip(),
                "charset4": self._charset4_var.get().strip(),
                "disable_potfile": self._disable_potfile_var.get(),
                "skip": self._skip_var.get().strip(),
                "limit": self._limit_var.get().strip(),
                "hashcat_dir": self._hc_path_var.get(),
                "jtr_dir": self._jtr_path_var.get(),
            }
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            log.warning("Failed to save config: %s", e)

    def _flush_save(self) -> None:
        """Cancel debounce and save immediately."""
        if self._save_debounce_id is not None:
            self.after_cancel(self._save_debounce_id)
            self._save_debounce_id = None
        self._do_save_config()

    def _load_config(self) -> None:
        if not CONFIG_FILE.exists():
            return
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            if data.get("hash"):
                self._hash_entry.insert(0, data["hash"])
                self._on_hash_changed()
            if data.get("wordlist"):
                self._wordlist_path = data["wordlist"]
                self._wl_path_label.configure(text=self._wordlist_path[-50:])
            if data.get("rules"):
                self._rule_paths = data["rules"]
                self._update_rule_label()
            if data.get("hash_file_path"):
                self._hash_file_path = data["hash_file_path"]
                self._hashfile_label.configure(text=f"📋 {Path(self._hash_file_path).name}")
            if data.get("mask"):
                self._mask_entry.insert(0, data["mask"])

            if data.get("attack_mode"): self._attack_mode_var.set(data["attack_mode"])
            if data.get("workload_profile"): self._workload_var.set(data["workload_profile"])
            if "optimized_kernel" in data: self._opt_kernel_var.set(data["optimized_kernel"])
            if data.get("session_name"): self._session_var.set(data["session_name"])
            if data.get("hwmon_temp_abort"): self._temp_abort_var.set(data["hwmon_temp_abort"])
            if data.get("charset1"): self._charset1_var.set(data["charset1"])
            if "disable_potfile" in data: self._disable_potfile_var.set(data["disable_potfile"])
            if data.get("skip"): self._skip_var.set(data["skip"])
            if data.get("limit"): self._limit_var.set(data["limit"])

            if data.get("device") and data["device"] in self._device_map.values():
                for k, v in self._device_map.items():
                    if v == data["device"]:
                        self._device_var.set(k)
                        break

            self._update_attack_payload_ui()
        except Exception as e:
            log.warning("Failed to load config: %s", e)

    def _clear_config(self) -> None:
        self._hash_entry.delete(0, "end")
        self._mask_entry.delete(0, "end")
        self._session_var.set("")
        self._temp_abort_var.set("90")
        self._charset1_var.set("")
        self._charset2_var.set("")
        self._charset3_var.set("")
        self._charset4_var.set("")
        self._disable_potfile_var.set(False)
        self._skip_var.set("")
        self._limit_var.set("")
        self._attack_mode_var.set("0 (Wordlist)")
        self._workload_var.set("3 (High)")
        self._opt_kernel_var.set(True)

        self._on_hash_changed()
        self._wordlist_path = None
        self._wl_path_label.configure(text="No file selected", text_color=COLOR_TEXT_DIM)
        self._rule_paths.clear()
        self._update_rule_label()
        self._hash_file_path = None
        self._hashfile_label.configure(text="")

        if self._device_list:
            self._device_var.set(list(self._device_map.keys())[0])
        self._update_attack_payload_ui()
        self._progress_bar.set(0)
        self._eta_label.configure(text="0%")

        if CONFIG_FILE.exists():
            try:
                CONFIG_FILE.unlink()
                self._term_clear()
                self._term_append("[+] Settings cleared.\n")
            except Exception as e:
                self._term_append(f"[!] Failed to delete config: {e}\n")

    def _on_closing(self) -> None:
        hashcat_stop()
        self._flush_save()
        self.destroy()


# ──────────────────────────────────────────────
#  Entry Point
# ──────────────────────────────────────────────

def main() -> None:
    setup_logging(debug="--debug" in __import__("sys").argv)
    log.info("Shatter starting…")
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    ShatterApp().mainloop()

if __name__ == "__main__":
    main()
