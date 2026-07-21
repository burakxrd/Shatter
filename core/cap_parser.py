"""
cap_parser.py — Scapy-based .cap/.pcap/.pcapng → hashcat hc22000 converter.

Parses WPA/WPA2 4-way EAPOL handshakes from capture files
and outputs hash lines in hashcat mode 22000 format:

  WPA*02*MIC*MAC_AP*MAC_STA*ESSID_HEX*NONCE_AP*EAPOL*MESSAGEPAIR

Scapy is imported lazily (only when a .cap file is actually parsed)
to avoid triggering Npcap/WinPcap UAC prompts on every program launch.
"""

import os
import struct


def _get_essid(pkt, Dot11Elt) -> str | None:
    """Extract ESSID from a Beacon or Probe Response frame."""
    elt = pkt.getlayer(Dot11Elt)
    while elt:
        if elt.ID == 0:  # SSID tag
            try:
                return elt.info.decode("utf-8", errors="replace")
            except Exception:
                return None
        elt = elt.payload.getlayer(Dot11Elt)
    return None


def _parse_eapol_key(raw_bytes: bytes) -> dict | None:
    """
    Parse an EAPOL-Key frame and extract fields.
    Layout (after EAPOL header ver+type+len = 4 bytes):
      [0]     Descriptor type
      [1:3]   Key Info
      [3:5]   Key Length
      [5:13]  Replay Counter
      [13:45] Nonce (32 bytes)
      [45:61] Key IV
      [61:69] Key RSC
      [69:77] Key ID
      [77:93] MIC (16 bytes)
      [93:95] Key Data Length
    """
    if len(raw_bytes) < 95:
        return None

    key_info = struct.unpack(">H", raw_bytes[1:3])[0]
    nonce = raw_bytes[13:45]
    mic = raw_bytes[77:93]

    is_pairwise = bool(key_info & 0x0008)
    has_install = bool(key_info & 0x0040)
    has_ack = bool(key_info & 0x0080)
    has_mic = bool(key_info & 0x0100)
    has_secure = bool(key_info & 0x0200)

    if not is_pairwise:
        return None

    # Message identification
    if has_ack and not has_mic:
        msg_num = 1
    elif not has_ack and has_mic and not has_secure:
        msg_num = 2
    elif has_ack and has_mic and has_install:
        msg_num = 3
    elif not has_ack and has_mic:
        msg_num = 4
    else:
        return None

    return {
        "msg_num": msg_num,
        "nonce": nonce,
        "mic": mic,
    }


def _load_scapy():
    """
    Lazy-load scapy with Npcap/WinPcap disabled.
    Returns (rdpcap, Dot11, Dot11Beacon, Dot11ProbeResp, Dot11Elt, EAPOL).
    """
    import logging
    logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
    logging.getLogger("scapy.loading").setLevel(logging.ERROR)

    # Block Npcap/WinPcap before scapy touches it
    os.environ["SCAPY_USE_LIBPCAP"] = "0"

    from scapy.config import conf
    conf.use_pcap = False
    conf.use_dnet = False
    conf.use_npcap = False

    from scapy.utils import rdpcap
    from scapy.layers.dot11 import Dot11, Dot11Beacon, Dot11ProbeResp, Dot11Elt
    from scapy.layers.eap import EAPOL

    return rdpcap, Dot11, Dot11Beacon, Dot11ProbeResp, Dot11Elt, EAPOL


def parse_cap_to_hc22000(filepath: str) -> list[str]:
    """
    Parse a .cap/.pcap/.pcapng file with scapy, extract WPA/WPA2
    handshakes, and return hash lines in hashcat 22000 format.
    """
    rdpcap, Dot11, Dot11Beacon, Dot11ProbeResp, Dot11Elt, EAPOL = _load_scapy()

    packets = rdpcap(filepath)

    # ── Pass 1: Collect ESSIDs from Beacons / Probe Responses ──
    essid_map: dict[str, str] = {}  # bssid → essid

    for pkt in packets:
        if pkt.haslayer(Dot11Beacon) or pkt.haslayer(Dot11ProbeResp):
            dot11 = pkt.getlayer(Dot11)
            if dot11:
                bssid = dot11.addr3
                if bssid:
                    essid = _get_essid(pkt, Dot11Elt)
                    if essid:
                        essid_map[bssid.lower()] = essid

    # ── Pass 2: Collect EAPOL key messages ──
    eapol_msgs: list[dict] = []

    for i, pkt in enumerate(packets):
        if not pkt.haslayer(EAPOL):
            continue

        dot11 = pkt.getlayer(Dot11)
        if not dot11:
            continue

        # Determine direction from flags
        to_ds = dot11.FCfield.to_DS if hasattr(dot11.FCfield, "to_DS") else (dot11.FCfield & 0x1)
        from_ds = dot11.FCfield.from_DS if hasattr(dot11.FCfield, "from_DS") else (dot11.FCfield & 0x2)

        if to_ds and not from_ds:
            mac_ap = dot11.addr1   # BSSID
            mac_sta = dot11.addr2  # STA
        elif from_ds and not to_ds:
            mac_sta = dot11.addr1  # STA
            mac_ap = dot11.addr2   # BSSID
        else:
            continue

        if not mac_ap or not mac_sta:
            continue

        # Full EAPOL frame bytes
        eapol_layer = pkt.getlayer(EAPOL)
        eapol_raw = bytes(eapol_layer)

        # Key descriptor starts after EAPOL header (4 bytes)
        key_data = eapol_raw[4:] if len(eapol_raw) > 4 else b""
        parsed = _parse_eapol_key(key_data)
        if not parsed:
            continue

        parsed["mac_ap"] = mac_ap.lower()
        parsed["mac_sta"] = mac_sta.lower()
        parsed["eapol_raw"] = eapol_raw
        parsed["pkt_index"] = i
        eapol_msgs.append(parsed)

    # ── Pass 3: Match handshake pairs and build hc22000 lines ──
    results: list[str] = []
    seen: set[str] = set()

    # Group by AP+STA pair
    pairs: dict[tuple[str, str], list[dict]] = {}
    for msg in eapol_msgs:
        key = (msg["mac_ap"], msg["mac_sta"])
        pairs.setdefault(key, []).append(msg)

    for (mac_ap, mac_sta), msgs in pairs.items():
        essid = essid_map.get(mac_ap, "")

        m1_m3 = [m for m in msgs if m["msg_num"] in (1, 3)]
        m2_list = [m for m in msgs if m["msg_num"] == 2]

        for m2 in m2_list:
            # Find best matching M1/M3 (closest before M2 in packet order)
            best = None
            for m in m1_m3:
                if m["pkt_index"] < m2["pkt_index"]:
                    if best is None or m["pkt_index"] > best["pkt_index"]:
                        best = m
            if best is None:
                continue

            anonce = best["nonce"]
            mic = m2["mic"]

            # Zero MIC in EAPOL frame copy
            eapol_frame = bytearray(m2["eapol_raw"])
            mic_offset = 4 + 77  # EAPOL hdr (4) + key descriptor offset to MIC (77)
            if len(eapol_frame) > mic_offset + 16:
                eapol_frame[mic_offset:mic_offset + 16] = b"\x00" * 16

            # Message pair value
            mp = 0 if best["msg_num"] == 1 else 2

            mac_ap_hex = mac_ap.replace(":", "")
            mac_sta_hex = mac_sta.replace(":", "")
            essid_hex = essid.encode("utf-8").hex()

            hash_line = (
                f"WPA*02*{mic.hex()}*{mac_ap_hex}*{mac_sta_hex}"
                f"*{essid_hex}*{anonce.hex()}*{bytes(eapol_frame).hex()}*{mp:02x}"
            )

            dedup_key = f"{mac_ap_hex}-{mac_sta_hex}-{anonce.hex()}"
            if dedup_key not in seen:
                seen.add(dedup_key)
                results.append(hash_line)

    return results


from core.result import ParseResult

def cap_to_hc22000_string(filepath: str) -> ParseResult:
    """
    Convenience wrapper: returns the hash lines or an error message.
    """
    try:
        hashes = parse_cap_to_hc22000(filepath)
        if not hashes:
            return ParseResult(error="No WPA/WPA2 handshake found in capture file.")
        return ParseResult(data="\n".join(hashes))
    except Exception as e:
        return ParseResult(error=f"Failed to parse capture file: {e}")
