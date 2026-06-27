"""ui_potfile.py â€” Potfile Manager tab (Mixin).

Reads hashcat.potfile and displays cracked hashes in a searchable,
scrollable list with copy-to-clipboard and clear functionality.

Performance features:
  - Debounced search (350ms) to avoid filtering on every keystroke
  - Paginated rendering (PAGE_SIZE rows at a time) to keep CTk responsive
"""

import logging
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from ui.theme import (
    FONT_LABEL, FONT_ENTRY, FONT_PATH, FONT_BUTTON,
    COLOR_ACCENT, COLOR_ACCENT_HOVER, COLOR_BG_DARK,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TERM_BG,
)

log = logging.getLogger(__name__)

PAGE_SIZE = 200          # Max rows rendered at once
SEARCH_DEBOUNCE_MS = 350  # Delay before filtering fires


def _get_potfile_path() -> Path:
    """Resolve potfile path dynamically from configured hashcat directory."""
    import core.tool_paths as _tp
    if _tp.hashcat_dir:
        return _tp.hashcat_dir / "hashcat.potfile"
    return Path(__file__).resolve().parent / "hashcat" / "hashcat.potfile"


def _parse_potfile(path: Path) -> list[tuple[str, str]]:
    """
    Parse hashcat.potfile into (hash, password) tuples.
    Format: hash_or_complex_fields:password  (password is always the last field)
    """
    entries: list[tuple[str, str]] = []
    if not path.exists():
        return entries
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            idx = line.rfind(":")
            if idx == -1:
                entries.append((line, "???"))
            else:
                entries.append((line[:idx], line[idx + 1:]))
    except Exception as e:
        log.error("Failed to parse potfile: %s", e)
    return entries


class PotfileMixin:
    """Mixin that adds _build_potfile() tab to ShatterApp."""

    def _build_potfile(self, parent) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        # â”€â”€ Toolbar â”€â”€
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")
        toolbar.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            toolbar, text="ğŸ”„ Yenile", font=FONT_BUTTON, fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER, corner_radius=10, height=36, width=120,
            command=self._potfile_refresh
        ).grid(row=0, column=0, padx=(0, 8))

        self._pot_search_var = ctk.StringVar()
        self._pot_search_var.trace_add("write", lambda *_: self._potfile_search_debounce())
        search = ctk.CTkEntry(
            toolbar, textvariable=self._pot_search_var,
            placeholder_text="ğŸ”  Ara (hash veya ÅŸifre)â€¦",
            font=FONT_ENTRY, height=36, corner_radius=10,
        )
        search.grid(row=0, column=1, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            toolbar, text="ğŸ—‘ï¸ Temizle", font=FONT_BUTTON,
            fg_color="#DC3545", hover_color="#A71D2A", corner_radius=10,
            height=36, width=110, command=self._potfile_clear
        ).grid(row=0, column=2)

        # â”€â”€ Stats â”€â”€
        self._pot_stats_label = ctk.CTkLabel(
            parent, text="", font=FONT_PATH, text_color=COLOR_TEXT_DIM, anchor="w"
        )
        self._pot_stats_label.grid(row=1, column=0, padx=14, sticky="w", pady=(0, 4))

        # â”€â”€ Scrollable List â”€â”€
        self._pot_scroll = ctk.CTkScrollableFrame(
            parent, fg_color=COLOR_TERM_BG, corner_radius=10,
            border_width=1, border_color="#30363D",
        )
        self._pot_scroll.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="nsew")
        self._pot_scroll.grid_columnconfigure(0, weight=2)
        self._pot_scroll.grid_columnconfigure(1, weight=1)
        self._pot_scroll.grid_columnconfigure(2, weight=0)

        # Internal state
        self._pot_entries: list[tuple[str, str]] = []
        self._pot_filtered: list[tuple[str, str]] = []
        self._pot_widgets: list[ctk.CTkFrame] = []
        self._pot_page: int = 0
        self._pot_search_timer: str | None = None

    # â”€â”€ Debounced Search â”€â”€

    def _potfile_search_debounce(self) -> None:
        """Cancel previous timer, schedule filter after SEARCH_DEBOUNCE_MS."""
        if self._pot_search_timer is not None:
            self.after_cancel(self._pot_search_timer)
        self._pot_search_timer = self.after(SEARCH_DEBOUNCE_MS, self._potfile_filter)

    def _potfile_filter(self) -> None:
        """Filter entries by search query and reset to page 0."""
        self._pot_search_timer = None
        query = self._pot_search_var.get().strip().lower()
        if not query:
            self._pot_filtered = self._pot_entries
        else:
            self._pot_filtered = [
                (h, p) for h, p in self._pot_entries
                if query in h.lower() or query in p.lower()
            ]
        self._pot_page = 0
        self._potfile_render()

    # â”€â”€ Refresh â”€â”€

    def _potfile_refresh(self) -> None:
        """Reload potfile from disk and rebuild the list."""
        self._pot_entries = _parse_potfile(_get_potfile_path())
        self._pot_filtered = self._pot_entries
        self._pot_search_var.set("")
        self._pot_page = 0
        self._potfile_render()
        log.info("Potfile refreshed: %d entries", len(self._pot_entries))

    # â”€â”€ Paginated Render â”€â”€

    def _potfile_render(self) -> None:
        """Clear and rebuild the scrollable list with current page of filtered entries."""
        # Destroy old widgets
        for w in self._pot_widgets:
            w.destroy()
        self._pot_widgets.clear()

        total = len(self._pot_entries)
        matched = len(self._pot_filtered)
        start = 0
        end = min((self._pot_page + 1) * PAGE_SIZE, matched)
        page_entries = self._pot_filtered[start:end]
        remaining = matched - end

        # Stats line
        if matched == total:
            stats = f"{end} / {total} kayÄ±t gÃ¶steriliyor"
        else:
            stats = f"{end} / {matched} eÅŸleÅŸme ({total} toplam)"
        stats += f"  â€¢  {_get_potfile_path().name}"
        self._pot_stats_label.configure(text=stats)

        if not page_entries:
            lbl = ctk.CTkLabel(
                self._pot_scroll, text="Potfile boÅŸ veya sonuÃ§ yok.",
                font=FONT_PATH, text_color=COLOR_TEXT_DIM,
            )
            lbl.grid(row=0, column=0, columnspan=3, pady=20)
            self._pot_widgets.append(lbl)
            return

        # Header
        hdr = ctk.CTkFrame(self._pot_scroll, fg_color="#1E293B", corner_radius=6, height=30)
        hdr.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 4))
        hdr.grid_columnconfigure(0, weight=2)
        hdr.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(hdr, text="  HASH", font=("Consolas", 11, "bold"), text_color="#94A3B8", anchor="w").grid(row=0, column=0, sticky="w", padx=8)
        ctk.CTkLabel(hdr, text="PASSWORD", font=("Consolas", 11, "bold"), text_color="#94A3B8", anchor="w").grid(row=0, column=1, sticky="w")
        self._pot_widgets.append(hdr)

        for i, (hash_val, password) in enumerate(page_entries):
            row_color = "#111827" if i % 2 == 0 else "#0F172A"
            rf = ctk.CTkFrame(self._pot_scroll, fg_color=row_color, corner_radius=4, height=32)
            rf.grid(row=i + 1, column=0, columnspan=3, sticky="ew", pady=1)
            rf.grid_columnconfigure(0, weight=2)
            rf.grid_columnconfigure(1, weight=1)

            h_display = hash_val if len(hash_val) <= 48 else f"{hash_val[:24]}â€¦{hash_val[-20:]}"
            ctk.CTkLabel(rf, text=f"  {h_display}", font=("Consolas", 11), text_color="#CBD5E1", anchor="w").grid(row=0, column=0, sticky="w", padx=4)
            ctk.CTkLabel(rf, text=password, font=("Consolas", 12, "bold"), text_color="#4ADE80", anchor="w").grid(row=0, column=1, sticky="w")

            ctk.CTkButton(
                rf, text="ğŸ“‹", width=32, height=26, corner_radius=6,
                fg_color="#334155", hover_color="#475569",
                command=lambda pw=password: self._potfile_copy(pw)
            ).grid(row=0, column=2, padx=4)

            self._pot_widgets.append(rf)

        # "Load More" button if there are remaining entries
        if remaining > 0:
            more_text = f"â–¼  {remaining} kayÄ±t daha gÃ¶ster  ({PAGE_SIZE}'ÅŸer)"
            more_btn = ctk.CTkButton(
                self._pot_scroll, text=more_text,
                font=("Consolas", 11, "bold"), fg_color="#1E293B",
                hover_color="#334155", corner_radius=8, height=36,
                command=self._potfile_load_more,
            )
            more_btn.grid(row=len(page_entries) + 1, column=0, columnspan=3,
                          sticky="ew", pady=(6, 4), padx=4)
            self._pot_widgets.append(more_btn)

    def _potfile_load_more(self) -> None:
        """Advance one page and re-render."""
        self._pot_page += 1
        self._potfile_render()

    # â”€â”€ Actions â”€â”€

    def _potfile_copy(self, text: str) -> None:
        """Copy text to clipboard."""
        self.clipboard_clear()
        self.clipboard_append(text)
        self._term_append(f"[+] Copied: {text}\n")

    def _potfile_clear(self) -> None:
        """Delete the potfile after confirmation."""
        pf = _get_potfile_path()
        if not pf.exists():
            self._term_append("[*] Potfile zaten boÅŸ.\n")
            return
        confirm = messagebox.askyesno(
            "Potfile Temizle",
            f"TÃ¼m kÄ±rÄ±lmÄ±ÅŸ ÅŸifre geÃ§miÅŸi silinecek.\n\n{pf}\n\nEmin misiniz?",
        )
        if confirm:
            try:
                pf.unlink()
                self._potfile_refresh()
                self._term_append("[+] Potfile temizlendi.\n")
                log.info("Potfile cleared by user.")
            except Exception as e:
                self._term_append(f"[!] Potfile silinemedi: {e}\n")
                log.error("Failed to clear potfile: %s", e)
