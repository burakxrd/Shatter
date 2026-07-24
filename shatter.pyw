"""
Shatter — Advanced Hash Cracker
Main application entry point.
"""

import logging
import sys
from pathlib import Path
import webview

from core import BUNDLE_DIR
from core.log_config import setup_logging
from ui.api import Api

log = logging.getLogger(__name__)

def main() -> None:
    setup_logging(debug="--debug" in sys.argv)
    log.info("Shatter starting…")

    # API Bridge
    api = Api()

    # Create frameless pywebview window
    html_path = str(BUNDLE_DIR / "ui" / "web" / "index.html")
    
    width = 1100
    height = 750
    x, y = None, None
    
    try:
        screens = webview.screens
        if screens:
            screen = screens[0]
            x = int((screen.width - width) / 2)
            y = int((screen.height - height) / 2)
    except Exception as e:
        log.debug("Could not center window: %s", e)
    
    window = webview.create_window(
        title="Shatter",
        url=html_path,
        js_api=api,
        width=width,
        height=height,
        x=x,
        y=y,
        min_size=(900, 650),
        frameless=True,
        easy_drag=False, # We handle drag via css class
    )
    
    api.set_window(window)
    
    # Start webview loop (blocks until closed)
    webview.start(debug="--debug" in sys.argv)

if __name__ == "__main__":
    main()
