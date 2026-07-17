"""
detector.py — Hash type detection using name-that-hash library.

Primary: name-that-hash (NTH) for 300+ hash types with popularity ranking.
Fallback: Hashcat-specific regex patterns for hashes NTH doesn't recognize
         (e.g., WPA*02, $pkzip2$, $keepass$, NetNTLM challenge/response, etc.)
"""

import re
from functools import lru_cache


# ──────────────────────────────────────────────
#  Hashcat-Only Fallback Patterns
#  These are hash formats that NTH does NOT reliably detect
#  but Hashcat supports. Tested empirically against NTH 1.11.
# ──────────────────────────────────────────────

_HASHCAT_FALLBACKS: list[tuple[re.Pattern, str]] = [
    # WPA/WPA2 PMKID/EAPOL (m=22000)
    (re.compile(r'^WPA\*'), "WPA/WPA2 PMKID/EAPOL (m=22000)"),

    # PKZIP variants
    (re.compile(r'^\$pkzip2?\$'), "PKZIP (m=17200)"),
    (re.compile(r'^\$zip2?\$'), "ZIP / WinZip (m=13600)"),

    # RAR
    (re.compile(r'^\$RAR3\$'), "RAR3-hp (m=12500)"),
    (re.compile(r'^\$rar5\$'), "RAR5 (m=13000)"),

    # 7-Zip
    (re.compile(r'^\$7z\$'), "7-Zip (m=11600)"),

    # PDF
    (re.compile(r'^\$pdf\$'), "PDF (m=10400)"),

    # MS Office
    (re.compile(r'^\$office\$'), "MS Office (m=9400)"),

    # KeePass
    (re.compile(r'^\$keepass\$'), "KeePass (m=13400)"),

    # BitLocker
    (re.compile(r'^\$bitlocker\$'), "BitLocker (m=22100)"),

    # VeraCrypt
    (re.compile(r'^\$veracrypt\$'), "VeraCrypt (m=13721)"),

    # LUKS
    (re.compile(r'^\$luks\$'), "LUKS (m=14600)"),

    # FileVault 2
    (re.compile(r'^\$fvde\$'), "FileVault 2 (m=16700)"),

    # 1Password
    (re.compile(r'^\$(1password|agilekeychain)\$'), "1Password (m=6600)"),

    # LastPass
    (re.compile(r'^\$lastpass\$'), "LastPass (m=6800)"),

    # Telegram Desktop
    (re.compile(r'^\$telegram\$'), "Telegram Desktop (m=22301)"),

    # Signal
    (re.compile(r'^\$signal\$'), "Signal (m=28200)"),

    # TACACS+
    (re.compile(r'^\$tacacs-plus\$'), "TACACS+ (m=16100)"),

    # SIP Digest
    (re.compile(r'^\$sip\$'), "SIP Digest Auth (m=11400)"),

    # SNMP v3
    (re.compile(r'^\$SNMPv3\$'), "SNMP v3 (m=26700)"),

    # DPAPI
    (re.compile(r'^\$DPAPImk\$'), "DPAPI masterkey (m=15300)"),

    # GRUB2
    (re.compile(r'^grub\.pbkdf2\.sha512'), "GRUB2 (m=7200)"),

    # Kerberos 5 variants
    (re.compile(r'^\$krb5tgs\$'), "Kerberos 5 TGS-REP (m=13100)"),
    (re.compile(r'^\$krb5asrep\$'), "Kerberos 5 AS-REP (m=18200)"),
    (re.compile(r'^\$krb5pa\$23\$'), "Kerberos 5 Pre-Auth (m=7500)"),
    (re.compile(r'^\$krb5pa\$17\$'), "Kerberos 5 AES128 (m=19600)"),
    (re.compile(r'^\$krb5pa\$18\$'), "Kerberos 5 AES256 (m=19700)"),

    # NetNTLMv2 (challenge/response format)
    (re.compile(r'^[^:]+::\S+:[a-fA-F0-9]{16}:[a-fA-F0-9]{32}:[a-fA-F0-9]+$'),
     "NetNTLMv2 (m=5600)"),

    # NetNTLMv1
    (re.compile(r'^[^:]+::\S+:[a-fA-F0-9]{48}:[a-fA-F0-9]{48}:[a-fA-F0-9]{16}$'),
     "NetNTLMv1 (m=5500)"),

    # IPMI2 RAKP
    (re.compile(r'^[a-f0-9]{40}:[a-f0-9]+:[a-f0-9]+:[a-f0-9]+$'),
     "IPMI2 RAKP (m=7300)"),

    # MSSQL 2012+
    (re.compile(r'^0x0200[a-fA-F0-9]{136}$', re.IGNORECASE), "MSSQL 2012+ (m=1731)"),

    # MSSQL 2005
    (re.compile(r'^0x0100[a-fA-F0-9]{88}$', re.IGNORECASE), "MSSQL 2005 (m=132)"),

    # MySQL 4.1+
    (re.compile(r'^\*[A-Fa-f0-9]{40}$'), "MySQL 4.1+ (m=300)"),

    # PostgreSQL MD5
    (re.compile(r'^md5[a-f0-9]{32}$'), "PostgreSQL MD5 (m=12)"),

    # macOS v10.8+
    (re.compile(r'^\$ml\$\d+\$[a-fA-F0-9]+\$[a-fA-F0-9]+$'), "macOS v10.8+ (m=7100)"),

    # Oracle 11g+
    (re.compile(r'^S:[A-Fa-f0-9]{60}$'), "Oracle 11g+ (m=112)"),

    # LDAP variants
    (re.compile(r'^\{SSHA\}'), "LDAP SSHA (m=111)"),
    (re.compile(r'^\{SSHA256\}'), "LDAP SSHA256 (m=1411)"),
    (re.compile(r'^\{SSHA512\}'), "LDAP SSHA512 (m=1711)"),

    # Cisco Type 8 / 9
    (re.compile(r'^\$8\$'), "Cisco Type 8 (m=9200)"),
    (re.compile(r'^\$9\$'), "Cisco Type 9 (m=9300)"),
]


def extract_m_value(detection_str: str) -> str | None:
    """Pull the first m=XXXX number from a detection string."""
    match = re.search(r'm=(\d+)', detection_str)
    return match.group(1) if match else None


@lru_cache(maxsize=128)
def detect_hash_type(hash_value: str) -> str:
    """
    Detect hash type(s) for a given hash string.

    Strategy:
        1. Try name-that-hash first (300+ types, popularity-ranked)
        2. Filter to only results that have a Hashcat mode
        3. If NTH finds nothing usable, fall back to Hashcat-specific regex patterns

    Results are cached (LRU, 128 entries) since this is called on every keystroke.

    Returns:
        Formatted string like "MD5 (m=0)  |  NTLM (m=1000)"
        or "Unknown / Custom" if nothing matches.
    """
    h = hash_value.strip()
    if not h:
        return "None"

    candidates: list[str] = []

    # ── Step 1: Hashcat-specific unambiguous patterns ──
    # Check these first, because NTH sometimes hallucinates on custom Hashcat formats
    # (e.g. $rar5$ being detected as SAP CODVN B).
    for pattern, label in _HASHCAT_FALLBACKS:
        if pattern.search(h):
            candidates.append(label)
            break

    # ── Step 2: name-that-hash (lazy import) ──
    # Only run if we didn't find a definitive Hashcat-specific match
    if not candidates:
        try:
            from name_that_hash import runner
            api_result = runner.api_return_hashes_as_dict([h])
            nth_matches = api_result.get(h, [])
        except Exception:
            nth_matches = []

        # Filter: only keep results with a valid Hashcat mode
        for match in nth_matches:
            hc_mode = match.get("hashcat")
            name = match.get("name", "Unknown")
            extended = match.get("extended", False)

            if hc_mode is not None and not extended:
                candidates.append(f"{name} (m={hc_mode})")

    # Limit to top 5 most popular to keep UI clean
    if len(candidates) > 5:
        candidates = candidates[:5]

    # ── De-duplicate while preserving order ──
    seen: set[str] = set()
    unique: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    if not unique:
        return "Unknown / Custom"

    return "  |  ".join(unique)
