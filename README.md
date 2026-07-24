<p align="center">
  <img src="assets/Shatter.png" alt="Shatter Logo" width="120">
</p>

<h1 align="center">Shatter</h1>

<p align="center">
  <strong>Advanced Hash Cracking Platform</strong><br>
  <em>Hashcat &amp; John the Ripper, unified under a single modern interface.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776ab?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/Platform-Windows-0078d4?logo=windows&logoColor=white" alt="Platform">
</p>

---

Shatter is a desktop GUI for Hashcat and John the Ripper built with Python + pywebview. Paste a hash, auto-detect the type, and crack it — no CLI required.

---

## Features

**Hash Detection**
- 300+ hash types via [name-that-hash](https://github.com/HashPals/Name-That-Hash) with 30+ additional Hashcat-specific regex fallback patterns
- Auto-maps to Hashcat `-m` mode with 300ms debounce as you type

**Encrypted File Extraction**
Pulls hashes directly from encrypted files using `*2john` tools: `.zip`, `.rar`, `.7z`, `.pdf`, `.docx/.xlsx/.pptx`, `.kdbx` (KeePass), `.ssh`, `.gpg`, `.pfx`

**PCAP Parsing**
Built-in Scapy-based WPA/WPA2 handshake parser for `.cap`, `.pcap`, `.pcapng` → outputs in hashcat mode 22000 format directly

**Attack Modes**
All 5 Hashcat modes (Wordlist, Combinator, Mask, Hybrid ×2) with multi-rule stacking, 4 custom charsets, and skip/limit for keyspace splitting

**Process Control**
Pause, Resume, Checkpoint (Save & Exit), Restore, Kill — all wired to the actual hashcat/john process via `psutil` and `CTRL_BREAK`

**Potfile Viewer**
Searchable table of cracked hash:password pairs from both `hashcat.potfile` and `john.pot`

**Auto Tool Setup**
Discovers Hashcat and JtR automatically on first run. If not found, downloads them from within the app.

---

## Architecture

```
Shatter/
├── shatter.pyw           # Entry point (pywebview window)
├── core/
│   ├── hc_engine.py      # Hashcat command building and execution
│   ├── jtr_engine.py     # John the Ripper command building and execution
│   ├── engine_base.py    # Abstract base class for engines
│   ├── crack_manager.py  # Orchestrates between Hashcat and JtR engines
│   ├── process.py        # Subprocess lifecycle (pause, resume, checkpoint, kill)
│   ├── detector.py       # Hash type detection (NTH + regex fallback)
│   ├── cap_parser.py     # Scapy-based .cap → hc22000 converter
│   ├── potfile_parser.py # Hashcat & JtR potfile parsing
│   ├── sanitizer.py      # CLI argument validation
│   ├── tool_paths.py     # Hashcat & JtR auto-discovery and validation
│   └── log_config.py     # Logging setup (rotating file + console)
├── ui/
│   ├── api.py            # Python ↔ JS bridge (pywebview js_api)
│   ├── api_crack.py      # Crack / restore / checkpoint mixin
│   ├── api_config.py     # Config and tool path management mixin
│   ├── api_download.py   # Hashcat & JtR download mixin
│   └── web/              # Frontend (HTML + CSS + vanilla JS)
├── tests/                # pytest test suite (98 tests)
└── temp/                 # Runtime config, sessions, logs
```

---

## Quick Start

**Portable (recommended)**

Download the latest release, extract, and run `Shatter.exe`. No installation required.

**From source**

```bash
git clone https://github.com/burakxrd/Shatter.git
cd Shatter
pip install -r requirements.txt
python shatter.pyw
```

Requires Python 3.11+. Hashcat and JtR can be configured or downloaded from within the app on first launch.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Legal Disclaimer

This tool is intended **solely for authorized security testing and research**. Unauthorized use against systems you do not own or have explicit permission to test is illegal.

---

## License

[MIT License](LICENSE)
