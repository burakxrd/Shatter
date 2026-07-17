# Changelog

All notable changes to Shatter will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] — 2026-07-17

### Added
- **Automatic Hash Detection** — 300+ hash types via name-that-hash + 30+ Hashcat-specific regex fallback patterns
- **Encrypted File Extraction** — Support for 12 formats (ZIP, RAR, 7z, PDF, Office, KeePass, SSH, GPG, PFX) via `*2john` tools
- **Native PCAP Parser** — Built-in Scapy-based WPA/WPA2 handshake parser → hashcat mode 22000 output
- **5 Attack Modes** — Straight, Combinator, Brute-force/Mask, Hybrid Wordlist+Mask, Hybrid Mask+Wordlist
- **Process Management** — Pause, Resume, Checkpoint (Save & Exit), Restore, Kill
- **Live Progress Tracking** — Real-time progress bar, speed, ETA, and recovered count from hashcat status output
- **Potfile Viewer** — Searchable table of cracked hash:password pairs with copy and clear
- **Automatic Tool Discovery** — Auto-finds Hashcat and JtR in common Windows paths, PATH, and user directories
- **Benchmark** — Quick MD5 + NTLM speed test on selected GPU device
- **Multi-Rule Stacking** — Apply multiple `.rule` files simultaneously
- **Custom Charsets** — 4 user-defined character sets
- **Skip / Limit** — Keyspace splitting support
- **Session Management** — Named sessions with checkpoint and restore
- **Modern UI** — pywebview + Tailwind CSS dark theme with frameless window
- **Structured Event Log** — Parsed hashcat output displayed as typed event cards
- **Rotating Log File** — 5 MB max with 3 backups in `temp/shatter.log`
- **Config Persistence** — Auto-save/restore of all settings via `temp/config.json`
