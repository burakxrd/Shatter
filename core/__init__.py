"""core — Backend logic package for Shatter.

Provides a single source of truth for the project root and temp directory.
Handles both development and PyInstaller frozen (portable) modes.
"""

import sys
from pathlib import Path

# When frozen by PyInstaller:
#   APP_ROOT    → directory containing the .exe (for user data: temp/, hashcat/, etc.)
#   BUNDLE_DIR  → sys._MEIPASS (where bundled assets live: ui/web/, core/, etc.)
#
# In development:
#   Both point to the project root.

if getattr(sys, "frozen", False):
    APP_ROOT = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    APP_ROOT = Path(__file__).resolve().parent.parent
    BUNDLE_DIR = APP_ROOT

TEMP_DIR = APP_ROOT / "temp"
TEMP_DIR.mkdir(exist_ok=True)
