# ⚡ Shatter — Advanced Hash Cracker

> **Hashcat & John the Ripper, tek bir modern arayüzde.**
> Hash yapıştır → otomatik algıla → tek tuşla kır.

Shatter, penetrasyon test uzmanları ve siber güvenlik araştırmacıları için geliştirilmiş, **Python + CustomTkinter** tabanlı bir masaüstü hash kırma platformudur. Sadece bir "GUI wrapper" değildir — otomatik hash algılama, şifreli dosyalardan hash çıkarımı, native PCAP parsing ve akıllı süreç yönetimi gibi özelliklerle CLI araçlarının üzerine gerçek bir zeka katmanı ekler.

---

## ✨ Özellikler

### 🔍 Otomatik Hash Algılama
- **name-that-hash** kütüphanesi ile 300+ hash tipini tanır (MD5, NTLM, SHA-256, bcrypt, vb.)
- NTH'nin kaçırdığı hash'ler için **30+ Hashcat-specific regex pattern**: WPA/WPA2 PMKID, PKZIP, RAR3/5, 7-Zip, PDF, MS Office, KeePass, BitLocker, VeraCrypt, Kerberos 5 (TGS/AS-REP), NetNTLMv1/v2, MSSQL, PostgreSQL, LDAP, Cisco ve daha fazlası
- Hash yapıştırıldığı anda debounce ile (300ms) anlık tespit ve Hashcat modu (`-m`) otomatik eşleme

### 📎 Şifreli Dosya Desteği
Aşağıdaki formatlardan `*2john` araçlarıyla otomatik hash çıkarımı:

| Format | Araç |
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

### 📡 Native PCAP Parser (Scapy)
`.cap`, `.pcap` ve `.pcapng` dosyaları için harici araç gerektirmeyen **yerleşik WPA/WPA2 handshake parser:**
- Scapy ile 802.11 paketlerini okur
- Beacon/Probe Response'lardan ESSID çıkarır
- EAPOL 4-way handshake'i (Message 1-4) parse eder
- Sonucu doğrudan **hashcat mode 22000** (`WPA*02*...`) formatında üretir
- Npcap/WinPcap UAC prompt'larını tetiklememek için **lazy import** kullanır

### ⚡ 5 Saldırı Modu
| Mod | Açıklama |
|-----|----------|
| `0` | Wordlist (klasik sözlük saldırısı) |
| `1` | Combinator (iki wordlist birleştirme) |
| `3` | Mask / Brute-force (`?a?a?a?a?d?d`) |
| `6` | Hybrid: Wordlist + Mask |
| `7` | Hybrid: Mask + Wordlist |

- **Multi-Rule Stacking:** Birden fazla `.rule` dosyasını üst üste uygulama
- **Custom Charset:** 4 adet kullanıcı tanımlı karakter seti (`-1`, `-2`, `-3`, `-4`)
- **Skip / Limit:** Keyspace bölme (dağıtık cracking temeli)

### 🎮 Süreç Yönetimi
- **Pause / Resume:** `psutil` ile hashcat sürecini dondurma ve devam ettirme
- **Checkpoint (Kaydet & Çık):** `CTRL_BREAK` sinyali ile hashcat'in `.restore` dosyası oluşturmasını sağlar
- **Restore:** Kaydedilmiş session'ı tek tuşla kaldığı yerden devam ettirir
- **Kill:** Anında durdurma
- **Canlı Progress Bar + ETA:** Hashcat `--status` çıktısından regex ile parse

### 📋 Potfile Viewer
- `hashcat.potfile` dosyasını parse edip kırılmış hash:password çiftlerini tabloda gösterir
- **Debounced arama** (350ms) — hash veya şifrede anlık filtreleme
- **Sayfalama (Pagination):** 200'er satırlık sayfalar ile büyük potfile'larda bile akıcı performans
- Tek tıkla panoya kopyalama
- Potfile temizleme (onaylı silme)

### 🔧 Araç Yolu Keşfi
- İlk çalışmada Hashcat ve JtR'yi **otomatik bulur:** yaygın Windows konumları + PATH + kullanıcı dizini
- Bulamazsa UI'dan seçtirtir, sonra config'e kayıt — bir daha sormaz
- `hashcat --version` ile doğrulama, `zip2john` varlığı ile JtR validasyonu

### ⏱️ Benchmark
Seçili GPU cihazında MD5 ve NTLM benchmark'ı çalıştırır — hızı terminalde gösterir.

---

## 🏗️ Mimari

```
Shatter/
├── shatter.pyw          # Ana giriş noktası (ShatterApp — Mixin tabanlı)
├── core/
│   ├── engine.py        # Hashcat süreç yönetimi, hash çıkarma, crack/benchmark/restore
│   ├── detector.py      # Hash tipi algılama (NTH + regex fallback)
│   ├── cap_parser.py    # Scapy tabanlı .cap → hc22000 dönüştürücü
│   ├── tool_paths.py    # Hashcat & JtR otomatik keşif ve validasyon
│   └── log_config.py    # Logging yapılandırması
├── ui/
│   ├── dashboard.py     # Dashboard tab (hash input, wordlist, crack button, progress)
│   ├── handlers.py      # Tüm event handler'lar (crack, restore, benchmark, pause, vb.)
│   ├── settings.py      # General & Advanced sekmesi (attack mode, workload, charset, vb.)
│   ├── potfile.py       # Potfile Manager tab (arama, sayfalama, kopyalama)
│   └── theme.py         # Renk paleti, fontlar, UI sabitleri
├── kernels/             # (Planlanan: özel hashcat kernel'ları)
├── tests/
│   ├── test_detector.py # Hash algılama unit testleri
│   ├── test_engine.py   # Engine unit testleri
│   ├── test_handlers.py # UI handler testleri
│   └── test_potfile.py  # Potfile parser testleri
└── temp/                # Geçici hash dosyaları, config.json
```

**Tasarım kararları:**
- **Mixin Pattern:** `ShatterApp`, `DashboardMixin`, `SettingsMixin`, `PotfileMixin` ve `HandlersMixin`'den türer — tek bir monolitik dosya yerine sorumluluk ayrımı
- **Threaded Execution:** Crack, benchmark ve restore işlemleri `threading.Thread(daemon=True)` ile arka planda çalışır, UI asla bloke olmaz
- **Lazy Import:** Scapy ve name-that-hash gibi ağır kütüphaneler sadece ihtiyaç duyulduğunda yüklenir

---

## 🚀 Kurulum

### Gereksinimler
- **Python 3.11+**
- **Hashcat** (indirip bir klasöre çıkar, Shatter otomatik bulur)
- **John the Ripper** (opsiyonel — şifreli dosyalardan hash çıkarmak için)

### Adımlar

```bash
# 1. Repo'yu klonla
git clone https://github.com/BurakOzsworthy/Shatter.git
cd Shatter

# 2. Bağımlılıkları kur
pip install customtkinter psutil name-that-hash scapy

# 3. Çalıştır
python shatter.pyw
```

> **Not:** İlk açılışta Hashcat bulunamazsa, uygulama seni General sekmesindeki "Tool Paths" bölümüne yönlendirir.

---

## 📸 Kullanım

1. **Hash yapıştır** → Algoritma otomatik algılanır
2. **Wordlist seç** veya **Mask yaz** (saldırı moduna göre)
3. **⚡ CRACK** butonuna bas
4. Terminalde canlı çıktı, progress bar'da ilerleme izle
5. Sonuç potfile'a yazılır → Potfile sekmesinden görebilirsin

**Şifreli dosya:** `📎 Extract` butonuyla `.zip`, `.rar`, `.pdf`, `.cap` vb. dosyalardan hash çıkar → otomatik algıla → kır.

---

## 🗺️ Yol Haritası (Roadmap)

### v1.2 — Kısa Vade
- [ ] 🧠 **Smart Attack Pipeline** — Tek tuşla otomatik saldırı zinciri: potfile check → top-100 şifre → rockyou+best64 → mask → hybrid
- [ ] 📊 **Canlı GPU Dashboard** — Sıcaklık, hız (MH/s), kırılan/toplam oranı gerçek zamanlı grafiklerle
- [ ] 📂 **Drag & Drop** — Hash, wordlist ve capture dosyalarını sürükle-bırak
- [ ] 🌐 **Wordlist Manager** — Popüler wordlist'leri tek tıkla indir (rockyou, kaonashi vb.) + CUPP benzeri özel liste oluşturucu

### v2.0 — Orta Vade
- [ ] 🤖 **AI Pattern Analizi** — Kırılan şifrelerden pattern çıkar, buna göre otomatik mask/rule üret
- [ ] 📁 **Proje / Kampanya Sistemi** — Hedef bazlı hash, wordlist ve sonuç yönetimi + PDF/HTML rapor export
- [ ] 🔌 **Plugin Sistemi** — `plugins/` klasöründen Python ile özel attack pipeline'ları

### v3.0 — Uzun Vade
- [ ] 📡 **Distributed Cracking** — LAN üzerinde otomatik keşifli, tek dosya worker agent ile basitleştirilmiş dağıtık kırma
- [ ] 🌐 **Web UI Alternatifi** — Tauri veya Electron tabanlı cross-platform arayüz

---

## 🆚 Neden Shatter?

| Özellik | hashcat-gui | Hashtopolis | CrackQ | **Shatter** |
|---------|:-----------:|:-----------:|:------:|:-----------:|
| Otomatik Hash Algılama | ❌ | ❌ | ❌ | ✅ 300+ tip |
| Şifreli Dosya Desteği | ❌ | ❌ | ❌ | ✅ 12 format |
| Native PCAP Parser | ❌ | ❌ | ❌ | ✅ Scapy |
| Pause / Resume / Checkpoint | ❌ | ⚠️ | ⚠️ | ✅ |
| Potfile Viewer | ❌ | ⚠️ | ❌ | ✅ Aranabilir |
| Kurulum | Kolay | Cehennem | Docker | `pip install` |
| Aktif Geliştirme | ❌ | ⚠️ | ❌ | ✅ |

---

## 🛡️ Yasal Uyarı

Bu araç **yalnızca yasal ve yetkili güvenlik testleri** için tasarlanmıştır. Yetkisiz sistemlere karşı kullanılması yasalara aykırıdır. Kullanıcı, aracın kullanımından doğan tüm sorumlulukları kabul eder.

---

## 📄 Lisans

MIT License — Detaylar için [LICENSE](LICENSE) dosyasına bakın.
