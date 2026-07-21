"""CLI argümanlarının mantıksal doğrulaması."""

import re
import logging

log = logging.getLogger(__name__)

# Argüman tipleri ve kuralları
_VALIDATORS = {
    "session_name": {
        "pattern": re.compile(r'^[a-zA-Z0-9_\-. ]+$'),
        "max_length": 64,
        "description": "Session name",
    },
    "workload_profile": {
        "pattern": re.compile(r'^[1-4]$'),
        "max_length": 1,
        "description": "Workload profile (1-4)",
    },
    "mask": {
        "pattern": re.compile(r'^[a-zA-Z0-9?!@#$%^&*\-_.,/\\:;|~\[\]{}()+= ]+$'),
        "max_length": 256,
        "description": "Mask pattern",
    },
}


def validate_cli_arg(arg_name: str, value: str) -> tuple[bool, str]:
    """CLI argümanını doğrular.
    
    Returns:
        (is_valid, error_message)
    """
    if not value or not value.strip():
        return False, f"{arg_name} cannot be empty."

    # Option injection koruması — '-' ile başlayan değerler
    if value.startswith("-"):
        return False, f"{arg_name} cannot start with '-' (potential option injection)."

    validator = _VALIDATORS.get(arg_name)
    if not validator:
        # Bilinmeyen argüman tipi — sadece uzunluk kontrolü
        if len(value) > 1024:
            return False, f"{arg_name} exceeds maximum length."
        return True, ""

    if len(value) > validator["max_length"]:
        return False, f"{validator['description']} exceeds max length ({validator['max_length']})."

    if not validator["pattern"].match(value):
        return False, f"{validator['description']} contains invalid characters."

    return True, ""
