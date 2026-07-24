"""ui/envelope.py — Standardised API response helpers.

Every public API method returns one of these envelopes so the JS
frontend can use a single error-handling path.
"""


def _ok(data=None) -> dict:
    if data is None:
        data = {}
    return {"success": True, "data": data, "error": None}


def _err(msg: str) -> dict:
    return {"success": False, "data": None, "error": msg}
