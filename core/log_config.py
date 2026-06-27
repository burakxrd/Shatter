"""core.log_config — Centralized logging setup for Shatter.

Call setup_logging() once at app startup to configure:
  - Console handler (WARNING+)  → user sees only important messages
  - File handler (DEBUG+)       → full debug trace in temp/shatter.log
  - Rotating file (5 MB max, 3 backups)
"""

import logging
import sys
from logging.handlers import RotatingFileHandler

from core import TEMP_DIR

LOG_FILE = TEMP_DIR / "shatter.log"
MAX_BYTES = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 3

FMT_FILE = "%(asctime)s  %(levelname)-8s  %(name)-18s  %(message)s"
FMT_CONSOLE = "%(levelname)-8s  %(name)s: %(message)s"


def setup_logging(*, debug: bool = False) -> None:
    """
    Configure root logger with console + rotating file handlers.

    Args:
        debug: If True, console also shows DEBUG level.
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Avoid duplicate handlers on repeated calls
    if root.handlers:
        return

    # ── File handler (full debug) ──
    fh = RotatingFileHandler(
        LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(FMT_FILE, datefmt="%Y-%m-%d %H:%M:%S"))
    root.addHandler(fh)

    # ── Console handler (warnings+ by default) ──
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.DEBUG if debug else logging.WARNING)
    ch.setFormatter(logging.Formatter(FMT_CONSOLE))
    root.addHandler(ch)

    logging.getLogger(__name__).info(
        "Logging initialized — file: %s  (debug=%s)", LOG_FILE, debug
    )
