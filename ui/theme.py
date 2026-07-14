"""theme.py — UI constants: colors, fonts, app configuration."""

APP_TITLE = "Shatter"
APP_GEOMETRY = "780x860"
APP_MIN_SIZE = (700, 740)

# Fonts
FONT_TERMINAL = ("Consolas", 12)
FONT_TITLE = ("Segoe UI", 28, "bold")
FONT_SUBTITLE = ("Segoe UI", 13)
FONT_LABEL = ("Segoe UI", 14)
FONT_ENTRY = ("Consolas", 14)
FONT_BUTTON = ("Segoe UI", 14, "bold")
FONT_CRACK = ("Segoe UI", 20, "bold")
FONT_PATH = ("Segoe UI", 12)
FONT_INFO = ("Segoe UI", 11, "italic")

# ── Color Palette (matches Shatter logo: teal shield + orange accent) ──
COLOR_TERM_BG = "#0F1923"
COLOR_TERM_FG = "#CBD5E1"

COLOR_ACCENT = "#10B981"        # Emerald/teal — primary (logo shield)
COLOR_ACCENT_HOVER = "#059669"  # Darker teal
COLOR_CRACK = "#F97316"         # Orange — main CTA (logo center eye)
COLOR_CRACK_HOVER = "#EA580C"   # Darker orange
COLOR_BG_DARK = "#0F172A"       # Slate-900 — deep dark background
COLOR_BG_CARD = "#1E293B"       # Slate-800 — card surfaces
COLOR_TEXT = "#E2E8F0"          # Slate-200 — primary text
COLOR_TEXT_DIM = "#94A3B8"      # Slate-400 — secondary text

# Attack mode options (value → display)
ATTACK_MODES = [
    "0 (Wordlist)",
    "1 (Combinator)",
    "3 (Mask/Brute-force)",
    "6 (Hybrid: Wordlist+Mask)",
    "7 (Hybrid: Mask+Wordlist)",
]

