"""ui_settings.py â€” General and Advanced settings tab builders (Mixin)."""

import customtkinter as ctk
from ui.theme import FONT_LABEL, FONT_INFO, COLOR_TEXT_DIM, ATTACK_MODES


class SettingsMixin:
    """Mixin that adds _build_general() and _build_advanced() to ShatterApp."""

    def _build_general(self, parent) -> None:
        parent.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(parent, text="Attack Mode (-a)", font=FONT_LABEL).grid(row=0, column=0, padx=16, pady=(16, 0), sticky="w")
        ctk.CTkOptionMenu(
            parent, values=ATTACK_MODES,
            variable=self._attack_mode_var, command=self._on_attack_mode_change
        ).grid(row=0, column=1, padx=16, pady=(16, 0), sticky="ew")
        ctk.CTkLabel(parent, text="0: Wordlist, 3: Mask, 6/7: Hybrid (Wordlist+Mask).", font=FONT_INFO, text_color=COLOR_TEXT_DIM).grid(row=1, column=1, padx=16, sticky="w")

        ctk.CTkLabel(parent, text="Workload Profile (-w)", font=FONT_LABEL).grid(row=2, column=0, padx=16, pady=(12, 0), sticky="w")
        ctk.CTkOptionMenu(
            parent, values=["1 (Low)", "2 (Default)", "3 (High)", "4 (Nightmare)"],
            variable=self._workload_var, command=lambda e: self._save_config()
        ).grid(row=2, column=1, padx=16, pady=(12, 0), sticky="ew")
        ctk.CTkLabel(parent, text="Nightmare (4) uses maximum GPU capacity.", font=FONT_INFO, text_color=COLOR_TEXT_DIM).grid(row=3, column=1, padx=16, sticky="w")

        ctk.CTkLabel(parent, text="Optimized Kernel (-O)", font=FONT_LABEL).grid(row=4, column=0, padx=16, pady=(12, 0), sticky="w")
        ctk.CTkSwitch(parent, text="Enable (Faster, max len 32)", variable=self._opt_kernel_var, command=self._save_config).grid(row=4, column=1, padx=16, pady=(12, 0), sticky="w")
        ctk.CTkLabel(parent, text="Enable if password is < 32 chars, ~20% speed increase.", font=FONT_INFO, text_color=COLOR_TEXT_DIM).grid(row=5, column=1, padx=16, sticky="w")

        ctk.CTkLabel(parent, text="Session Name (--session)", font=FONT_LABEL).grid(row=6, column=0, padx=16, pady=(12, 0), sticky="w")
        e = ctk.CTkEntry(parent, textvariable=self._session_var, placeholder_text="my_session")
        e.grid(row=6, column=1, padx=16, pady=(12, 0), sticky="ew")
        e.bind("<KeyRelease>", lambda e: self._save_config())
        ctk.CTkLabel(parent, text="You can resume a stopped job with the same session name.", font=FONT_INFO, text_color=COLOR_TEXT_DIM).grid(row=7, column=1, padx=16, sticky="w")

        # ── Tool Paths ──
        sep = ctk.CTkFrame(parent, fg_color="#334155", height=1)
        sep.grid(row=8, column=0, columnspan=2, padx=16, pady=(16, 4), sticky="ew")

        ctk.CTkLabel(parent, text="🔧  Tool Paths", font=("Segoe UI", 15, "bold")).grid(row=9, column=0, columnspan=2, padx=16, pady=(4, 0), sticky="w")

        # Hashcat
        ctk.CTkLabel(parent, text="Hashcat Folder", font=FONT_LABEL).grid(row=10, column=0, padx=16, pady=(10, 0), sticky="w")
        hc_frame = ctk.CTkFrame(parent, fg_color="transparent")
        hc_frame.grid(row=10, column=1, padx=16, pady=(10, 0), sticky="ew")
        hc_frame.grid_columnconfigure(0, weight=1)
        self._hc_entry = ctk.CTkEntry(hc_frame, textvariable=self._hc_path_var, placeholder_text="C:\\hashcat")
        self._hc_entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(hc_frame, text="📁", width=40, height=32, command=self._browse_hashcat).grid(row=0, column=1)
        self._hc_status = ctk.CTkLabel(parent, text="", font=FONT_INFO, text_color="#4ADE80")
        self._hc_status.grid(row=11, column=1, padx=16, sticky="w")

        # JtR
        ctk.CTkLabel(parent, text="JtR Run Folder", font=FONT_LABEL).grid(row=12, column=0, padx=16, pady=(8, 0), sticky="w")
        jtr_frame = ctk.CTkFrame(parent, fg_color="transparent")
        jtr_frame.grid(row=12, column=1, padx=16, pady=(8, 0), sticky="ew")
        jtr_frame.grid_columnconfigure(0, weight=1)
        self._jtr_entry = ctk.CTkEntry(jtr_frame, textvariable=self._jtr_path_var, placeholder_text="C:\\john\\run")
        self._jtr_entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(jtr_frame, text="📁", width=40, height=32, command=self._browse_jtr).grid(row=0, column=1)
        self._jtr_status = ctk.CTkLabel(parent, text="", font=FONT_INFO, text_color="#4ADE80")
        self._jtr_status.grid(row=13, column=1, padx=16, sticky="w")

        # Update status after both widgets exist
        self._update_tool_status()

    def _browse_hashcat(self) -> None:
        from tkinter import filedialog
        import core.tool_paths as tool_paths
        d = filedialog.askdirectory(title="Select Hashcat Folder")
        if d and tool_paths.set_hashcat_dir(d):
            self._hc_path_var.set(str(tool_paths.hashcat_dir))
            self._save_config()
            self._update_tool_status()
            self._term_append(f"[+] Hashcat found: {tool_paths.hashcat_exe}\n")
        elif d:
            self._term_append(f"[!] Invalid hashcat folder: {d}\n")

    def _browse_jtr(self) -> None:
        from tkinter import filedialog
        import core.tool_paths as tool_paths
        d = filedialog.askdirectory(title="Select JtR 'run' Folder")
        if d and tool_paths.set_jtr_dir(d):
            self._jtr_path_var.set(str(tool_paths.jtr_dir))
            self._save_config()
            self._update_tool_status()
            self._term_append(f"[+] JtR found: {tool_paths.jtr_dir}\n")
        elif d:
            self._term_append(f"[!] Invalid JtR folder: {d}\n")

    def _update_tool_status(self) -> None:
        import core.tool_paths as tool_paths
        if tool_paths.hashcat_exe:
            self._hc_status.configure(text=f"✅ {tool_paths.hashcat_exe.name} found", text_color="#4ADE80")
        else:
            self._hc_status.configure(text="❌ Not found", text_color="#FF6B6B")
        if tool_paths.jtr_dir:
            self._jtr_status.configure(text=f"✅ {tool_paths.jtr_dir.name}/ found", text_color="#4ADE80")
        else:
            self._jtr_status.configure(text="⚠️ Not found (optional)", text_color="#FFA500")

    def _build_advanced(self, parent) -> None:
        parent.grid_columnconfigure(1, weight=1)
        vcmd = (self.register(self._validate_number), '%P')

        ctk.CTkLabel(parent, text="Max Temp (--hwmon-temp-abort)", font=FONT_LABEL).grid(row=0, column=0, padx=16, pady=(16, 0), sticky="w")
        ctk.CTkOptionMenu(
            parent, values=["70", "75", "80", "85", "90", "95", "100"],
            variable=self._temp_abort_var, command=lambda e: self._save_config()
        ).grid(row=0, column=1, padx=16, pady=(16, 0), sticky="ew")
        ctk.CTkLabel(parent, text="Process is aborted if GPU reaches this temperature.", font=FONT_INFO, text_color=COLOR_TEXT_DIM).grid(row=1, column=1, padx=16, sticky="w")

        ctk.CTkLabel(parent, text="Custom Charset 1 (-1)", font=FONT_LABEL).grid(row=2, column=0, padx=16, pady=(12, 0), sticky="w")
        e2 = ctk.CTkEntry(parent, textvariable=self._charset1_var, placeholder_text="e.g., ?l?d?u")
        e2.grid(row=2, column=1, padx=16, pady=(12, 0), sticky="ew")
        e2.bind("<KeyRelease>", lambda e: self._save_config())
        ctk.CTkLabel(parent, text="Character pool for '-1' in mask.", font=FONT_INFO, text_color=COLOR_TEXT_DIM).grid(row=3, column=1, padx=16, sticky="w")

        ctk.CTkLabel(parent, text="Disable Potfile", font=FONT_LABEL).grid(row=4, column=0, padx=16, pady=(12, 0), sticky="w")
        ctk.CTkSwitch(parent, text="Ignore previous cracks", variable=self._disable_potfile_var, command=self._save_config).grid(row=4, column=1, padx=16, pady=(12, 0), sticky="w")
        ctk.CTkLabel(parent, text="Ignores previously cracked passwords.", font=FONT_INFO, text_color=COLOR_TEXT_DIM).grid(row=5, column=1, padx=16, sticky="w")

        ctk.CTkLabel(parent, text="Skip (-s)", font=FONT_LABEL).grid(row=6, column=0, padx=16, pady=(12, 0), sticky="w")
        e4 = ctk.CTkEntry(parent, textvariable=self._skip_var, placeholder_text="0", validate="key", validatecommand=vcmd)
        e4.grid(row=6, column=1, padx=16, pady=(12, 0), sticky="ew")
        e4.bind("<KeyRelease>", lambda e: self._save_config())

        ctk.CTkLabel(parent, text="Limit (-l)", font=FONT_LABEL).grid(row=8, column=0, padx=16, pady=(12, 0), sticky="w")
        e5 = ctk.CTkEntry(parent, textvariable=self._limit_var, placeholder_text="0 (unlimited)", validate="key", validatecommand=vcmd)
        e5.grid(row=8, column=1, padx=16, pady=(12, 0), sticky="ew")
        e5.bind("<KeyRelease>", lambda e: self._save_config())

    def _validate_number(self, value_if_allowed: str) -> bool:
        return value_if_allowed == "" or value_if_allowed.isdigit()
