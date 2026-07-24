# Changelog

All notable changes to Shatter will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.1.0] — 2026-07-24

### Fixed
- **Checkpoint / Save & Exit** — Replaced `CREATE_NO_WINDOW` with `SW_HIDE` so hashcat's `CTRL_BREAK` handler works correctly; checkpoint now reliably saves the session
- **Restore session tracking** — `run_restore` now correctly sets `_last_session` / `_last_restore_file` so "Session saved" confirmation appears after a checkpoint on a restored session
- **Restore file dialog** — File browser now opens directly in `temp/sessions/` instead of the hashcat install folder
- **Extract Hash — JtR guard** — `.txt` / plain hash files no longer blocked by "JtR not configured" error; JtR is only required for packet capture files (`.cap`, `.pcap`, `.pcapng`)
- **Tool path validation warning** — When a configured tool path fails validation, a visible warning is shown in the UI instead of silently accepting a broken path
- **`is_running` race window on restore** — `_starting` flag is now set before `run_restore` begins, eliminating a brief window where the UI could show the session as idle
- **`on_done` callback exceptions** — Exceptions thrown inside `on_done` are now logged instead of silently swallowed
- **`detect_hash` empty input** — Empty or whitespace-only hash strings no longer reach the detection library
- **Window resize bounds** — `resize()` clamps values to 400–4096 × 300–2160 to prevent invalid window states
- **Session name with spaces** — Session names containing spaces are now rejected by the sanitizer (spaces break hashcat CLI argument parsing)

### Improved
- **`run_crack` / `run_restore` unified** — Shared output and completion callbacks extracted into `_make_output_callback()` / `_make_done_callback()`; fixes applied once now cover both code paths
- **`is_running` performance** — `psutil` system-wide process scan is cached for 1 second, reducing CPU overhead during active polling
- **Code quality** — All Turkish-language comments and docstrings translated to English

### Tests
- Added `test_api_crack.py` (19 tests) — callback behaviour, session saved logic, `run_restore` / `run_crack` API, checkpoint
- Added `test_engine_restore.py` (25 tests) — exit code messages, session dedup, `_run_hashcat` tracking, restore command construction, `on_done` guarantee

---

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
