"""Module for reading and parsing Hashcat and JtR potfiles."""

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def parse_hashcat_potfile(pot_path: Path) -> list[dict]:
    """Reads Hashcat potfile. Isolates errors on each line.
    
    Hashcat potfile format: HASH:PLAINTEXT
    """
    entries = []
    if not pot_path or not pot_path.exists():
        return entries

    try:
        with open(pot_path, "r", encoding="utf-8", errors="replace") as f:
            for line_num, raw_line in enumerate(f, 1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    entry = _parse_hc_potline(line)
                    if entry:
                        entries.append(entry)
                except (ValueError, IndexError) as e:
                    log.debug("Skipping HC potfile line %d: %s", line_num, e)
    except OSError as e:
        log.error("Failed to read hashcat potfile %s: %s", pot_path, e)

    return entries


def parse_jtr_potfile(pot_path: Path) -> list[dict]:
    """Reads JtR potfile. Format differs from Hashcat.
    
    JtR potfile format: $FORMAT$HASH:PLAINTEXT
    May also contain $HEX$(...) encoded passwords.
    """
    entries = []
    if not pot_path or not pot_path.exists():
        return entries

    try:
        with open(pot_path, "r", encoding="utf-8", errors="replace") as f:
            for line_num, raw_line in enumerate(f, 1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    entry = _parse_jtr_potline(line)
                    if entry:
                        entries.append(entry)
                except (ValueError, IndexError) as e:
                    log.debug("Skipping JtR potfile line %d: %s", line_num, e)
    except OSError as e:
        log.error("Failed to read JtR potfile %s: %s", pot_path, e)

    return entries


def _parse_hc_potline(line: str) -> dict | None:
    """Parses a single Hashcat potfile line.
    
    Hashcat format is usually: hash:plain
    
    Using rsplit: password can contain ':' BUT hash format is fixed.
    Hashcat's logic: the last ':' is the separator (rsplit is correct).
    """
    if ":" not in line:
        return None

    # Hashcat potfile: HASH:PLAIN — last ':' is the separator
    h, p = line.rsplit(":", 1)
    if not h:
        return None

    p = _decode_hex_password(p)
    return {"hash": h, "password": p, "source": "hashcat"}


def _parse_jtr_potline(line: str) -> dict | None:
    """Parses a single JtR potfile line.
    
    JtR format: USER:$FORMAT$HASH:PLAIN or $FORMAT$HASH:PLAIN
    The first ':' is usually after the hash, but the format is complex.
    In JtR, the last ':' is also usually the password.
    """
    if ":" not in line:
        return None

    h, p = line.rsplit(":", 1)
    if not h:
        return None

    p = _decode_hex_password(p)
    return {"hash": h, "password": p, "source": "jtr"}


def _decode_hex_password(pwd: str) -> str:
    """Decodes passwords in $HEX[...] format."""
    pwd = pwd.strip()
    if pwd.startswith("$HEX[") and pwd.endswith("]"):
        try:
            return bytes.fromhex(pwd[5:-1]).decode("utf-8", errors="replace")
        except ValueError:
            return pwd  # Return raw string if decoding fails
    return pwd
