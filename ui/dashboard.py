"""ui_dashboard.py — Dashboard tab builder (Mixin)."""

import customtkinter as ctk
from ui.theme import (
    FONT_LABEL, FONT_ENTRY, FONT_BUTTON, FONT_CRACK, FONT_PATH,
    COLOR_ACCENT, COLOR_ACCENT_HOVER, COLOR_CRACK, COLOR_CRACK_HOVER,
    COLOR_BG_DARK, COLOR_TEXT, COLOR_TEXT_DIM,
)


class DashboardMixin:
    """Mixin that adds _build_dashboard() to ShatterApp."""

    def _build_dashboard(self, parent) -> None:
        parent.grid_columnconfigure(0, weight=1)
        row = 0

        # ── Hash Input Row ──
        ctk.CTkLabel(parent, text="Target Hash", font=FONT_LABEL, text_color=COLOR_TEXT, anchor="w").grid(
            row=row, column=0, padx=16, sticky="w", pady=(8, 0))
        row += 1

        hf = ctk.CTkFrame(parent, fg_color="transparent")
        hf.grid(row=row, column=0, padx=16, sticky="ew", pady=(4, 2))
        hf.grid_columnconfigure(0, weight=1)

        self._hash_entry = ctk.CTkEntry(hf, placeholder_text="Paste hash or load file…",
            font=FONT_ENTRY, height=42, corner_radius=10, border_width=1, border_color=COLOR_ACCENT)
        self._hash_entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self._hash_entry.bind("<KeyRelease>", self._on_hash_changed)

        ctk.CTkButton(hf, text="📎 Extract", font=("Segoe UI", 12, "bold"),
            fg_color="#2D6A4F", hover_color="#1B4332", corner_radius=10, height=42, width=100,
            command=self._on_extract_hash).grid(row=0, column=1, padx=(0, 4))

        ctk.CTkButton(hf, text="📋 Hash File", font=("Segoe UI", 12, "bold"),
            fg_color="#7B2D8E", hover_color="#5A1F6A", corner_radius=10, height=42, width=110,
            command=self._on_load_hash_file).grid(row=0, column=2)
        row += 1

        # ── Algo Detection + Hash File indicator ──
        self._algo_label = ctk.CTkLabel(parent, text="Detected Algorithm:  None",
            font=FONT_PATH, text_color=COLOR_TEXT_DIM, anchor="w")
        self._algo_label.grid(row=row, column=0, padx=18, sticky="w", pady=(2, 0))
        row += 1

        self._hashfile_label = ctk.CTkLabel(parent, text="", font=FONT_PATH, text_color="#C084FC", anchor="w")
        self._hashfile_label.grid(row=row, column=0, padx=18, sticky="w", pady=(0, 6))
        row += 1

        # ── Wordlist / Mask Payload Frame ──
        self._attack_payload_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._attack_payload_frame.grid(row=row, column=0, padx=16, sticky="ew", pady=4)
        self._attack_payload_frame.grid_columnconfigure(1, weight=1)
        row += 1

        self._wl_button = ctk.CTkButton(self._attack_payload_frame, text="📂  Wordlist", font=FONT_BUTTON,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, corner_radius=10, height=38, width=160,
            command=self._on_select_wordlist)
        self._wl_path_label = ctk.CTkLabel(self._attack_payload_frame, text="No file selected",
            font=FONT_PATH, text_color=COLOR_TEXT_DIM, anchor="w")

        self._mask_entry = ctk.CTkEntry(self._attack_payload_frame, placeholder_text="Mask: ?a?a?a?a",
            font=FONT_ENTRY, height=38, corner_radius=10)
        self._mask_entry.bind("<KeyRelease>", lambda e: self._save_config())

        # ── Rule Selector (multi-rule) ──
        self._rule_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._rule_frame.grid(row=row, column=0, padx=16, sticky="ew", pady=4)
        self._rule_frame.grid_columnconfigure(1, weight=1)
        row += 1

        rbf = ctk.CTkFrame(self._rule_frame, fg_color="transparent")
        rbf.grid(row=0, column=0)
        ctk.CTkButton(rbf, text="📂 Add Rule", font=FONT_BUTTON, fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER, corner_radius=10, height=38, width=140,
            command=self._on_add_rule).grid(row=0, column=0, padx=(0, 4))
        ctk.CTkButton(rbf, text="✕", font=("Segoe UI", 14, "bold"), fg_color="#555",
            hover_color="#777", corner_radius=10, height=38, width=38,
            command=self._on_clear_rules).grid(row=0, column=1)

        self._rule_path_label = ctk.CTkLabel(self._rule_frame, text="No rules",
            font=FONT_PATH, text_color=COLOR_TEXT_DIM, anchor="w")
        self._rule_path_label.grid(row=0, column=1, padx=(12, 0), sticky="w")

        self._update_attack_payload_ui()

        # ── Device + Benchmark ──
        df = ctk.CTkFrame(parent, fg_color="transparent")
        df.grid(row=row, column=0, padx=16, sticky="ew", pady=(10, 4))
        df.grid_columnconfigure(0, weight=1)
        row += 1

        self._device_var.set(list(self._device_map.keys())[0] if self._device_map else "")
        self._device_menu = ctk.CTkOptionMenu(df, values=list(self._device_map.keys()),
            variable=self._device_var, font=FONT_PATH, fg_color=COLOR_BG_DARK,
            button_color=COLOR_ACCENT, button_hover_color=COLOR_ACCENT_HOVER,
            corner_radius=10, height=38, dynamic_resizing=False, command=lambda e: self._save_config())
        self._device_menu.grid(row=0, column=0, sticky="ew", padx=(0, 12))

        self._bench_button = ctk.CTkButton(df, text="⏱️ Speed Test", font=("Segoe UI", 13, "bold"),
            fg_color="#F39C12", hover_color="#D68910", corner_radius=10, height=38, width=140,
            command=self._on_benchmark)
        self._bench_button.grid(row=0, column=1)

        # ── Progress Bar + ETA ──
        pf = ctk.CTkFrame(parent, fg_color="transparent")
        pf.grid(row=row, column=0, padx=16, sticky="ew", pady=(8, 0))
        pf.grid_columnconfigure(0, weight=1)
        row += 1

        self._progress_bar = ctk.CTkProgressBar(pf, height=14, corner_radius=6,
            fg_color="#1E293B", progress_color="#6C63FF")
        self._progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self._progress_bar.set(0)

        self._eta_label = ctk.CTkLabel(pf, text="0%", font=("Consolas", 12, "bold"),
            text_color=COLOR_TEXT_DIM, width=200, anchor="e")
        self._eta_label.grid(row=0, column=1)

        # ── CRACK + RESTORE ──
        af = ctk.CTkFrame(parent, fg_color="transparent")
        af.grid(row=row, column=0, padx=16, sticky="ew", pady=(12, 4))
        af.grid_columnconfigure(0, weight=3)
        af.grid_columnconfigure(1, weight=1)
        row += 1

        self._crack_button = ctk.CTkButton(af, text="⚡  CRACK", font=FONT_CRACK,
            fg_color=COLOR_CRACK, hover_color=COLOR_CRACK_HOVER, corner_radius=12, height=52,
            command=self._on_crack)
        self._crack_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self._restore_button = ctk.CTkButton(af, text="🔄 RESTORE", font=("Segoe UI", 16, "bold"),
            fg_color="#0D6EFD", hover_color="#0A58CA", corner_radius=12, height=52,
            command=self._on_restore)
        self._restore_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        row += 1

        # ── Process Control Bar (hidden until crack starts) ──
        self._control_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._control_frame.grid(row=row, column=0, padx=16, sticky="ew", pady=(0, 8))
        self._control_frame.grid_columnconfigure((0, 1, 2), weight=1)
        self._control_frame.grid_remove()

        self._stop_button = ctk.CTkButton(self._control_frame, text="🛑  Durdur",
            font=("Segoe UI", 13, "bold"), fg_color="#DC3545", hover_color="#A71D2A",
            corner_radius=10, height=38, command=self._on_stop)
        self._stop_button.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self._pause_button = ctk.CTkButton(self._control_frame, text="⏸  Mola",
            font=("Segoe UI", 13, "bold"), fg_color="#FD7E14", hover_color="#D36B0B",
            corner_radius=10, height=38, command=self._on_pause_toggle)
        self._pause_button.grid(row=0, column=1, padx=4, sticky="ew")

        self._checkpoint_button = ctk.CTkButton(self._control_frame, text="💾  Kaydet & Çık",
            font=("Segoe UI", 13, "bold"), fg_color="#0D6EFD", hover_color="#0A58CA",
            corner_radius=10, height=38, command=self._on_checkpoint)
        self._checkpoint_button.grid(row=0, column=2, padx=(4, 0), sticky="ew")

    def _update_attack_payload_ui(self) -> None:
        """Show/hide wordlist and mask fields based on selected attack mode."""
        mode = self._attack_mode_var.get()
        for w in self._attack_payload_frame.winfo_children():
            w.grid_forget()

        if mode.startswith("3"):
            # Mask only
            self._mask_entry.grid(row=0, column=0, columnspan=2, sticky="ew")
            try: self._rule_frame.grid_remove()
            except Exception: pass
        elif mode.startswith("6") or mode.startswith("7"):
            # Hybrid: wordlist + mask side by side
            self._wl_button.grid(row=0, column=0)
            self._wl_path_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=(0, 8))
            self._mask_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0))
            try: self._rule_frame.grid_remove()
            except Exception: pass
        else:
            # Wordlist modes (0, 1)
            self._wl_button.grid(row=0, column=0)
            self._wl_path_label.grid(row=0, column=1, padx=(12, 0), sticky="w")
            try: self._rule_frame.grid()
            except Exception: pass
