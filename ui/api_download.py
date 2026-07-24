import json
import logging
import threading

from core import APP_ROOT
import core.tool_paths as tool_paths

log = logging.getLogger(__name__)

from ui.envelope import _ok, _err

class DownloadMixin:
    """Download manager mixin'i."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dl_lock = threading.Lock()
        self._downloading = False
        self._cancel_download = threading.Event()

    def download_hashcat(self) -> dict:
        with self._dl_lock:
            if self._downloading:
                if hasattr(self, "_error_response"):
                    return self._error_response("A download is already in progress.")
                return _err("A download is already in progress.")
            self._downloading = True
        self._cancel_download.clear()

        def _do():
            try:
                from core.downloader import download_hashcat as dl_hashcat
                dest = APP_ROOT / "hashcat"

                def on_progress(downloaded, total):
                    if hasattr(self, "_window") and self._window and total > 0:
                        pct = round(downloaded / total * 100, 1)
                        self._window.evaluate_js(
                            f"onDownloadProgress('hashcat', {pct}, {downloaded}, {total})"
                        )

                hc_dir = dl_hashcat(dest, on_progress, self._cancel_download.is_set)
                tool_paths.set_hashcat_dir(str(hc_dir))
                if hasattr(self, "_sync_engine_paths"):
                    self._sync_engine_paths()

                if hasattr(self, "_window") and self._window:
                    safe_path = json.dumps(str(hc_dir))
                    self._window.evaluate_js(
                        f"onDownloadDone('hashcat', true, {safe_path})"
                    )
            except InterruptedError:
                log.info("Hashcat download cancelled by user.")
                if hasattr(self, "_window") and self._window:
                    self._window.evaluate_js(
                        "onDownloadDone('hashcat', false, 'Download cancelled.')"
                    )
            except Exception as e:
                log.exception("Hashcat download failed")
                if hasattr(self, "_window") and self._window:
                    safe_err = json.dumps(str(e))
                    self._window.evaluate_js(
                        f"onDownloadDone('hashcat', false, {safe_err})"
                    )
            finally:
                with self._dl_lock:
                    self._downloading = False

        threading.Thread(target=_do, daemon=True).start()
        return _ok({"status": "downloading"})

    def download_jtr(self) -> dict:
        with self._dl_lock:
            if self._downloading:
                if hasattr(self, "_error_response"):
                    return self._error_response("A download is already in progress.")
                return _err("A download is already in progress.")
            self._downloading = True
        self._cancel_download.clear()

        def _do():
            try:
                from core.downloader import download_jtr as dl_jtr
                dest = APP_ROOT / "johntheripper"

                def on_progress(downloaded, total):
                    if hasattr(self, "_window") and self._window and total > 0:
                        pct = round(downloaded / total * 100, 1)
                        self._window.evaluate_js(
                            f"onDownloadProgress('jtr', {pct}, {downloaded}, {total})"
                        )

                jtr_dir = dl_jtr(dest, on_progress, self._cancel_download.is_set)
                tool_paths.set_jtr_dir(str(jtr_dir))
                if hasattr(self, "_sync_engine_paths"):
                    self._sync_engine_paths()

                if hasattr(self, "_window") and self._window:
                    safe_path = json.dumps(str(jtr_dir))
                    self._window.evaluate_js(
                        f"onDownloadDone('jtr', true, {safe_path})"
                    )
            except InterruptedError:
                log.info("JtR download cancelled by user.")
                if hasattr(self, "_window") and self._window:
                    self._window.evaluate_js(
                        "onDownloadDone('jtr', false, 'Download cancelled.')"
                    )
            except Exception as e:
                log.exception("JtR download failed")
                if hasattr(self, "_window") and self._window:
                    safe_err = json.dumps(str(e))
                    self._window.evaluate_js(
                        f"onDownloadDone('jtr', false, {safe_err})"
                    )
            finally:
                with self._dl_lock:
                    self._downloading = False

        threading.Thread(target=_do, daemon=True).start()
        return _ok({"status": "downloading"})

    def cancel_download(self) -> dict:
        self._cancel_download.set()
        return _ok()
