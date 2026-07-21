"""Hashcat ve JtR potfile dosyalarını okuyup parse eden modül."""

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def parse_hashcat_potfile(pot_path: Path) -> list[dict]:
    """Hashcat potfile'ı okur. Her satırdaki hataları izole eder.
    
    Hashcat potfile formatı: HASH:PLAINTEXT
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
    """JtR potfile'ı okur. Formatı Hashcat'ten farklıdır.
    
    JtR potfile formatı: $FORMAT$HASH:PLAINTEXT
    Ayrıca $HEX$(...) encode'lu şifreler olabilir.
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
    """Tek bir Hashcat potfile satırını parse eder.
    
    Hashcat formatı genelde: hash:plain
    $HEX[...] encoding'i desteklenir.
    rsplit kullanımı: şifre ':' içerebilir AMA hash'in formatı belirli.
    Hashcat'in kendi mantığı: son ':' ayırıcıdır (rsplit doğru).
    """
    if ":" not in line:
        return None

    # Hashcat potfile: HASH:PLAIN — son ':' ayırıcıdır
    h, p = line.rsplit(":", 1)
    if not h:
        return None

    p = _decode_hex_password(p)
    return {"hash": h, "password": p, "source": "hashcat"}


def _parse_jtr_potline(line: str) -> dict | None:
    """Tek bir JtR potfile satırını parse eder.
    
    JtR formatı: USER:$FORMAT$HASH:PLAIN veya $FORMAT$HASH:PLAIN
    İlk ':' genelde hash sonrasıdır ama format karmaşık.
    JtR'da da son ':' genelde password'dür.
    """
    if ":" not in line:
        return None

    h, p = line.rsplit(":", 1)
    if not h:
        return None

    p = _decode_hex_password(p)
    return {"hash": h, "password": p, "source": "jtr"}


def _decode_hex_password(pwd: str) -> str:
    """$HEX[...] formatındaki şifreleri decode eder."""
    pwd = pwd.strip()
    if pwd.startswith("$HEX[") and pwd.endswith("]"):
        try:
            return bytes.fromhex(pwd[5:-1]).decode("utf-8", errors="replace")
        except ValueError:
            return pwd  # Decode başarısızsa ham string döndür
    return pwd
