<p align="center">
  <img src="assets/Shatter.png" alt="Shatter Logo" width="120">
</p>

<h1 align="center">Shatter</h1>

<p align="center">
  <strong>Advanced Hash Cracking Platform</strong><br>
  <em>Hashcat & John the Ripper, unified under a single modern interface.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776ab?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/Platform-Windows-0078d4?logo=windows&logoColor=white" alt="Platform">
  <img src="https://img.shields.io/badge/UI-pywebview-orange" alt="UI">
</p>

---

## What is Shatter?

Shatter is a desktop hash cracking platform built with **Python + pywebview**, designed for penetration testers and security researchers. It's not just a GUI wrapper — it adds a real intelligence layer on top of CLI tools with automatic hash detection, encrypted file extraction, native PCAP parsing, and smart process management.

**Paste a hash → auto-detect → crack with one click.**

---

## ✨ Features

### 🔍 Automatic Hash Detection
- Identifies **300+ hash types** via [name-that-hash](https://github.com/HashPals/Name-That-Hash) (MD5, NTLM, SHA-256, bcrypt, etc.)
- **30+ Hashcat-specific regex patterns** for hashes NTH misses: WPA/WPA2 PMKID, PKZIP, RAR3/5, 7-Zip, PDF, MS Office, KeePass, BitLocker, VeraCrypt, Kerberos 5, NetNTLMv1/v2, and more
- Instant detection with **300ms debounce** as you type, with automatic Hashcat mode (`-m`) mapping

### 📎 Encrypted File Support
Automatic hash extraction from encrypted files using `*2john` tools:

| Format | Tool |
|--------|------|
| `.zip` | zip2john |
| `.rar` | rar2john |
| `.7z` | 7z2john |
| `.pdf` | pdf2john |
| `.docx` `.xlsx` `.pptx` `.doc` `.xls` | office2john |
| `.kdbx` (KeePass) | keepass2john |
| `.ssh` | ssh2john |
| `.gpg` | gpg2john |
| `.pfx` | pfx2john |

### 📡 Native PCAP Parser
Built-in WPA/WPA2 handshake parser for `.cap`, `.pcap`, and `.pcapng` files — no external tools needed:
- Reads 802.11 packets with Scapy
- Extracts ESSID from Beacon/Probe Response frames
- Parses EAPOL 4-way handshake (Messages 1-4)
- Outputs directly in **hashcat mode 22000** (`WPA*02*...`) format
- Uses **lazy import** to avoid triggering Npcap/WinPcap UAC prompts

### ⚡ 5 Attack Modes
| Mode | Description |
|------|-------------|
| `0` | Wordlist (classic dictionary attack) |
| `1` | Combinator (two wordlists combined) |
| `3` | Mask / Brute-force (`?a?a?a?a?d?d`) |
| `6` | Hybrid: Wordlist + Mask |
| `7` | Hybrid: Mask + Wordlist |

- **Multi-Rule Stacking:** Apply multiple `.rule` files
- **Custom Charsets:** 4 user-defined character sets (`-1` to `-4`)
- **Skip / Limit:** Keyspace splitting for distributed cracking

### 🎮 Process Management
- **Pause / Resume:** Freeze and unfreeze the hashcat process via `psutil`
- **Checkpoint (Save & Exit):** `CTRL_BREAK` signal for hashcat's `.restore` file
- **Restore:** Resume a saved session with one click
- **Kill:** Instant termination
- **Live Progress Bar + ETA:** Parsed from hashcat `--status` output

### 📋 Potfile Viewer
- Parses `hashcat.potfile` and `john.pot` — displays cracked hash:password pairs from both engines in a searchable table
- One-click copy to clipboard
- Potfile clearing with confirmation

### 🔧 Automatic Tool Discovery
- Auto-discovers Hashcat and JtR on first run: common Windows paths + PATH + user directories
- Falls back to manual selection via UI, then saves to config — never asks again
- Validates with `hashcat --version` and `zip2john` presence checks

---

## 🏗️ Architecture

```
Shatter/
├── shatter.pyw          # Entry point (pywebview window)
├── core/
│   ├── hc_engine.py     # Hashcat command building and execution
│   ├── jtr_engine.py    # John the Ripper command building and execution
│   ├── engine_base.py   # Abstract base class for engines
│   ├── crack_manager.py # Orchestrates between Hashcat and JtR engines
│   ├── process.py       # Subprocess lifecycle (pause, resume, checkpoint, kill)
│   ├── detector.py      # Hash type detection (NTH + regex fallback)
│   ├── cap_parser.py    # Scapy-based .cap → hc22000 converter
│   ├── potfile_parser.py# Hashcat & JtR potfile parsing
│   ├── sanitizer.py     # CLI argument validation
│   ├── tool_paths.py    # Hashcat & JtR auto-discovery and validation
│   └── log_config.py    # Logging configuration (rotating file + console)
├── ui/
│   ├── api.py           # Python ↔ JS bridge (pywebview js_api)
│   ├── api_crack.py     # Crack / restore / checkpoint mixin
│   ├── api_config.py    # Config and tool path management mixin
│   ├── api_download.py  # Hashcat & JtR download mixin
│   └── web/             # Frontend (HTML + CSS + vanilla JS)
├── tests/               # pytest test suite (98 tests)
└── temp/                # Runtime config, hash files, sessions, logs
```

**Key design decisions:**
- **pywebview + HTML/JS Frontend:** Native-feeling desktop app with a modern web UI
- **Structured Event Parsing:** Raw hashcat output is parsed into typed events (progress, speed, cracked, etc.) and dispatched to the frontend
- **Threaded Execution:** Crack, benchmark, and restore run in `daemon=True` threads — UI never blocks
- **Lazy Imports:** Heavy libraries (Scapy, name-that-hash) are loaded only when needed

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.11+**
- **Hashcat** (path can be configured in-app if not in PATH)
- **John the Ripper** (optional — for `*2john` encrypted file extraction)

### Installation

```bash
# Clone the repository
git clone https://github.com/burakxrd/Shatter.git
cd Shatter

# Install dependencies
pip install -r requirements.txt

# Launch
python shatter.pyw
```

> **Note:** On first launch, if Hashcat isn't found automatically, you'll be prompted to set the path in Settings → Tool Paths.

---

## 📸 Usage

1. **Paste a hash** → Algorithm is auto-detected
2. **Select a wordlist** or **enter a mask** (depending on attack mode)
3. **Hit ⚡ CRACK**
4. Watch live output in the Event Log, track progress on the progress bar
5. Results are saved to the potfile → view them in the Activity tab

**Encrypted files:** Use the `📎 Extract from File` button to pull hashes from `.zip`, `.rar`, `.pdf`, `.cap` and more → auto-detect → crack.

---

## 🆚 Why Shatter?

| Feature | hashcat-gui | Hashtopolis | CrackQ | **Shatter** |
|---------|:-----------:|:-----------:|:------:|:-----------:|
| Auto Hash Detection | ❌ | ❌ | ❌ | ✅ 300+ types |
| Encrypted File Support | ❌ | ❌ | ❌ | ✅ 12 formats |
| Native PCAP Parser | ❌ | ❌ | ❌ | ✅ Scapy |
| Pause / Resume / Checkpoint | ❌ | ⚠️ | ⚠️ | ✅ |
| Potfile Viewer | ❌ | ⚠️ | ❌ | ✅ Searchable |
| Setup Difficulty | Easy | Complex | Docker | `pip install` |
| Active Development | ❌ | ⚠️ | ❌ | ✅ |

---

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 🛡️ Legal Disclaimer

This tool is intended **solely for authorized security testing and research**. Unauthorized use against systems you do not own or have explicit permission to test is illegal. The user assumes full responsibility for how this tool is used.

---

## 📄 License

[MIT License](LICENSE) — see the LICENSE file for details.
