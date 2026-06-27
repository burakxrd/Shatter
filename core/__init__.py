"""core — Backend logic package for Shatter.

Provides a single source of truth for the project root and temp directory.
"""

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
TEMP_DIR = APP_ROOT / "temp"
TEMP_DIR.mkdir(exist_ok=True)
