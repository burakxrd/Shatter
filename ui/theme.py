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

# Colors
COLOR_TERM_BG = "#0D1117"
COLOR_TERM_FG = "#39FF14"

COLOR_ACCENT = "#6C63FF"
COLOR_ACCENT_HOVER = "#5A52D9"
COLOR_CRACK = "#FF4C6A"
COLOR_CRACK_HOVER = "#D93A56"
COLOR_BG_DARK = "#1A1A2E"
COLOR_BG_CARD = "#16213E"
COLOR_TEXT = "#E0E0E0"
COLOR_TEXT_DIM = "#8D8D9B"

# Attack mode options (value → display)
ATTACK_MODES = [
    "0 (Wordlist)",
    "1 (Combinator)",
    "3 (Mask/Brute-force)",
    "6 (Hybrid: Wordlist+Mask)",
    "7 (Hybrid: Mask+Wordlist)",
]
