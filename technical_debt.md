# Shatter - Technical Debt & Bugs

Bu belge sistemdeki "sessizce başarısız olan" (silent failure) ve şans eseri çalışan kritik hataları (bug) listelemektedir.

| Hata (Bug) Açıklaması | Dosya Adı |
| :--- | :--- |
| **Kayıp Motor Mantığı (Fallback Hatası):** `_on_engine_output` fonksiyonu, aktif motor ismi tam olarak "jtr" değilse (örn: yanlış yazılmışsa veya None ise) hata vermek yerine sessizce Hashcat parser'ına yönlendiriyor. | `ui/api.py` |
| **Hata Gösterimi Race Condition:** `_error_response` bir hata bastırmak istediğinde henüz bir motor çalışmıyorsa (`active_engine_name == None`), loglar yanlışlıkla Hashcat parser'ına gidiyor. İki parser'ın `[!]` işaretini tesadüfen aynı şekilde silmesi sayesinde çalışıyor gibi görünüyor. | `ui/api.py` |
| **Tembel Hash Tespiti:** Bir hash'in birden fazla ihtimali olduğunda (`detect_hash_type`), `extract_m_value` fonksiyonu sadece gördüğü **ilk** `m=XXXX` değerini alıp diğer haklı ihtimalleri çöpe atıyor. | `core/detector.py` |
| **Potfile Hata Yutması (Exception Swallowing):** `get_potfile` okuma yaparken tek bir hatalı/bozuk satırla karşılaşırsa, hatayı yutup okumayı tamamen kesiyor ve dosyanın geri kalanındaki sağlam şifreleri ekrana getirmiyor. | `ui/api.py` |
| **Ayar Dosyası Bozulması Gizleme:** `get_config` fonksiyonu, okuma sırasında bir hata (örneğin bozuk JSON) çıkarsa kullanıcıyı "Ayarlarınız bozuldu" diye uyarmak yerine sessizce varsayılan (boş) ayarları yüklüyor. | `ui/api.py` |
| **Devasa God Node Problemi:** `Api` sınıfı 33 bağlantı ile indirme, boyutlandırma, ayarlar, hash kırma gibi tamamen farklı sorumlulukları tek başına yönetiyor (Single Responsibility prensibi ihlali). | `ui/api.py` |
| **Düşük Modül İçi Uyum (Low Cohesion):** "Hashcat Engine Core" (0.10 skor), içerisindeki çekirdek motor mantığının birbirleriyle zayıf bağlantılı ve dağınık olduğunu gösteriyor. | `core/` |
| **Başıboş Frontend Bileşenleri:** `terminal`, `bridge`, `store` gibi 36 düğümün grafikte izole/kopuk görünmesi, belgelenmemiş veya spagettiye dönmüş Javascript mimarisine işaret ediyor. | `ui/web/app.js` |
| **Fazla Yüklenmiş Köprüler (Overloaded Bridges):** `CrackManager` (20) ve `HashcatEngine` (21) kendi işlerini yapmak yerine diğer modüller arası veri taşıyıcı (hammal) görevi görüyor. | `core/crack_manager.py` |
| **Gizli Bağımlılıklar (Inferred Dependencies):** Sınıfların birbirlerini güvenli ve doğrudan arayüzlerle değil, dolaylı çağırması "state senkronizasyonu" ve yarış durumu (race condition) hatalarına açıktır. | Tüm Mimari |
| **Tutarsız Hata Yönetimi:** Başarı için `_ok()` doğru yerde dururken, hata yöneten `_err()` bambaşka alakasız bir topluluğa kaymış; dağınık hata yönetimi sessiz başarısızlıklara ve arayüz donmalarına yol açabilir. | `ui/api.py` |
| **Gereksiz Yan Etkiler (Side Effects):** Sadece cihazları listeleme veya benchmark gibi okuma (read) işlemlerinde bile `_sync_engine_paths()` çağrılarak uygulamanın gereksiz yere yorulması ve state'in mutasyona uğratılması. | `ui/api.py` |
| **Pencere Boyutlandırma (IPC) Darboğazı:** `setupResize` fonksiyonunda pencere sürüklenirken saniyede 60 kez backend IPC çağrısı (`bridge.resize`) yapılması ciddi arayüz kasmalarına neden olur. | `ui/web/app.js` |
| **Zombie Process (Ölü Süreç) UI Kilidi:** `stopCrack()` çağrıldığında arayüz `window.onCrackDone` sinyalini bekler. Backend asılı kalırsa (zombie process), UI sonsuza kadar kilitli kalır. | `ui/web/app.js` |
| **Cihaz Yükleme (Dropdown) Takılması:** `loadDevices` hata fırlatır veya null dönerse sessizce sonlanır, `<option>` kısmı "Loading devices..." olarak sonsuza kadar asılı kalır. | `ui/web/app.js` |
| **Set Tipi Bellek Sızıntısı (Memory Leak):** `TerminalManager`'daki `_crackedPasswords` Set objesi DOM temizlense bile büyümeye devam eder, günlerce süren ataklarda JS belleğini şişirir. | `ui/web/app.js` |
| **Ayar Kaybı (Debounce Race Condition):** `SettingsStore` debounce süresi (500ms) dolmadan uygulama kapatılırsa `beforeunload` tahliyesi olmadığı için son ayarlar kalıcı olarak kaybolur. | `ui/web/app.js` |
| **Kapsülleme (Encapsulation) İhlali:** `TerminalManager` doğrudan global `updateProgress`'i çağırarak sınıfın bağımsızlığını yok eder (spagetti koda yol açar). | `ui/web/app.js` |
| **Ana İş Parçacığı (Main Thread) Bloklanması:** `loadHashFile`/`extractHash` büyük dosyalarda senkron çalışarak Pywebview ve Python ana thread'ini kilitler, "Yanıt Vermiyor" hatasına düşürür. | `ui/api.py` & `core/extractor.py` |
| **Sessiz API Hataları (Null Return):** `HashcatBridge._call` içindeki try-catch sadece Toast gösterip null döner, zincirleme çağıran asenkron fonksiyonlar mantıksal akışı yarım bırakır. | `ui/web/app.js` |
