# Mevcut KADO için bağlantı eklentisi 0.1.1

Kullanıcının gönderdiği gerçek `BASLAT.bat`, `BASLAT.ps1` ve `sistem/main.py` incelendi. Başlatma zinciri `BASLAT.bat → BASLAT.ps1 → sistem/.venv/Scripts/python.exe main.py`. Ana sınıf `KadoLive`; Gemini araç yönlendiricisi `_execute_tool`, model araç yapılandırması `_build_config`.

İncelenen `main.py` SHA-256: `9c952052a8b02e87a7176064ba00c7e0ddd40ef8cc1eef8145e3f6dea60118a6`. Dosya değişmişse eklenti çalışmayı reddeder; yeni sürüm ayrıca incelenmelidir.

## Ne değişir?

Yeni AI Company klasörüne `kado_bridge/local_host.py`, iki yeni BAT başlatıcısı ve PowerShell başlatıcısı eklenir. Backend'e zaman aşımı olan KADO bağlantı sinyali eklenir. Var olan panelin bağlantılar sayfası bu gerçek sinyali okur. Panel dosyaları, veritabanı, API anahtarı ve kullanıcı görevleri değiştirilmez.

**Eski `C:\KADO\kado` ve `C:\KADO\KADO-AJANLAR` kaynak dosyaları değiştirilmez.** Mevcut KADO'nun `.venv` ortamına paket yüklenmez. Yeni başlatıcı, incelenmiş `main.py` dosyasını mevcut KADO Python ortamında yükler; sınıfın üç yöntemine yalnızca süreç belleğinde şirket adaptörü ekler. KADO'nun orijinal kimliği, sistem talimatı, ses ayarları, hafıza ve eski araçları korunur.

Orijinal KADO normal çalışırken kendi hafıza ve günlük dosyalarını kullanmayı sürdürür. Bu eklentinin orijinal kaynakları değiştirmemesi, KADO'nun normal veri yazmalarının engellendiği anlamına gelmez.

## Kurulum ve ilk yerel test

1. Bağlantı güncellemesi ZIP'ini ayrı bir klasöre çıkarıp `KADO_BAGLANTI_KUR.bat` çalıştırın. Yeni AI Company klasörü bulunamazsa seçmeniz istenir.
2. Kurucu yalnızca yeni AI Company'nin doğrulanmış süreç durdurma betiğini kullanır; eski KADO'yu veya diğer Python süreçlerini durdurmaz. Değiştireceği yeni şirket dosyalarını önce `data/backups/kado-integration-...` altına yedekler.
3. Yeni şirket paneli yeniden başlatıldıktan sonra `KADO_35_BAGLANTI_TESTI.bat` ile API ve kaynak hash kontrolü yapılabilir. Bu kontrol eski KADO'yu başlatmaz ve ses testi sayılmaz.
4. Açık eski KADO penceresini normal şekilde kapatın. Yeni AI Company klasöründeki `KADO_35_AJAN_BASLAT.bat` dosyasını çalıştırın. Eski `BASLAT.bat` kullanılabilir; fakat o normal başlangıca şirket araçlarını eklemez.
5. KADO'ya yazılı veya sesli olarak **“Yeni 35 ajanlı şirket bağlantısını kontrol et.”** deyin. Modelin `company_connection_status` araç çağrısını yaptığını doğrulayın.
6. **“Yeni şirkete çalışma alanı dosya denetimi görevi ver; yol nokta olsun.”** deyin. Yeni panelde UUID görev kaydı, gerçek araçlar, QA ve denetim kanıtı oluşmalıdır. Başlangıç metninin anlaşılması canlı modelle kullanıcı makinesinde ayrıca doğrulanır.

Sesli görev için mevcut KADO'nun kendi Gemini Live bağlantısının çalışması gerekir. Eklenti Gemini anahtarı veya ElevenLabs sesi oluşturmaz. Mevcut KADO'nun ses yapılandırmasını kullanır.

## Eklenen araçlar

`company_connection_status`, `company_list_agents`, `company_workspace_audit`, `company_generate_text`, `company_get_task`, `company_recent_tasks`, `company_control_task`.

Eski sayısal görev kimlikleri ve eski ajan araçları korunur. Yeni şirket UUID kullanır. İnsan onayı yeni sesli kontrol aracından verilemez; panelden inceleme gerekir. Sağlayıcı bağlı değilse metin üretimi `BLOCKED` olur.

KADO'nun gönderdiği görevler `data/kado-host-state.json` ile izlenir. Sonuç yeni KADO arayüzünün günlüğüne yazılır. Mevcut ElevenLabs kuyruğu etkin ve ses kapalı değilse kısa bildirim o kuyruğa verilir. Kuyruğa verilmesi sesin karşı tarafta duyulduğunun kanıtı değildir. `_pc_notify` kullanılmaz; bu eski yöntem WhatsApp'a iletim yapabildiği için doğrulanmamış dış gönderim başlatılmaz.

## Bağlantı durumunun anlamı

Backend, çalışan adaptörün 8 saniyede bir gönderdiği kimlik doğrulanmış sinyali izler. Son 35 saniyede `host_ready` veya `tool_call_verified` sinyali yoksa bağlantı çevrimdışı gösterilir. Bu, adaptör bağlantısını gösterir; mikrofon, ElevenLabs, gerçek Gemini yanıtı veya WhatsApp araması doğrulaması değildir.

## Geri alma

Eski KADO'nun kendi `BASLAT.bat` dosyası her zaman özgün başlangıç yoludur. Güncelleme klasöründeki `KADO_BAGLANTI_GERI_AL.bat` yalnızca bu eklentinin yeni AI Company klasörüne yaptığı son dosya değişikliklerini yedekten geri alır. Sonradan değiştirilmiş dosyayı otomatik ezmez. Veritabanı, token, WhatsApp oturumu ve eski KADO kaynaklarına dokunmaz.

## Test sınırları

Linux'ta gerçek backend/HTTP kuyruğu ve yüklenen kaynak yöntemlerinden çıkarılan sözleşmeler test edilir. Google GenAI tipleriyle araç şeması ve eski araçlara geri dönüş kontrol edilir. Windows ses donanımı, çalışan gerçek KADO arayüzü, Gemini Live, ElevenLabs ve WhatsApp bu ortamda bulunmadığından saha testleri tamamlanmış sayılmaz. WhatsApp köprüsünün gerçek `bridge.js`, `worker.py` ve arama taşıma kodu henüz incelenmemiştir; bu eklenti WhatsApp araması sağlamaz.
