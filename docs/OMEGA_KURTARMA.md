# KADO OMEGA — kaynak envanteri ve doğrulama

## İncelenen kaynak

14 Kasım 2026, `cinoom02-star/KADO`, başlangıç commit'i `e40b4b7158a14b444ce69c3f4a9c66adc1afc58c` (`KADO kaynakları`). Eklenen metin gereksinim belgesidir; ayrı ZIP yüklenmedi. Depodaki kaynaklar incelendi. Kullanıcının Windows diski, dışarıda kalan hafıza ve model dosyaları burada mevcut değildir.

Başlangıç sürümü 797 izlenen dosya içeriyor: `kado/` 244, `KADO-AJANLAR/` 362, `KADO-AI-COMPANY/` 85, `yedek_20261111/` 89, `yukle/` 6 ve 11 kök dosyası. Güvenli kod taramasında 335 Python/JS/TS/başlatıcı dosyası, bunların içinde 259 Python dosyası ve 87 birebir aynı içerikli dosya grubu bulundu. Gizli oturum içerikleri bu taramada okunmadı. Kod imzaları bir yeteneğin çalıştığının kanıtı sayılmadı.

Depoda izlenen SQLite veritabanı yok. Bu, eski kullanıcı hafızasının boş olduğu anlamına gelmez: `.gitignore` veritabanı, hafıza ve veri klasörlerini dışlıyor. Influencer Studio altında 19 JSON, 8 TXT, 7 PNG, 2 JPG ve diğer yardımcı dosyalar mevcut; ses/video model ağırlıklarının varlığı doğrulanmadı.

## Bileşen sınıflandırması

Durum kodları: 1 doğrulandı (belirtilen kapsamda), 2 kod var/çalışması doğrulanmadı, 3 kısmi, 4 hatalı (belirtilen kullanımda), 5 eksik, 6 plan, 7 eski/mükerrer. Bir bileşenin self-testinin geçmesi gerçek donanım ve dış servis doğrulaması değildir.

| Bileşen / gerçek yol | Durum | Kanıt ve sınır |
| --- | --- | --- |
| `kado/sistem/main.py`, `tool_defs.py`, `actions/` | 2 | Sesli ana uygulama ve araçlar var. `main.py` hash'i mevcut Company adaptörünün beklediği hash ile aynı; ses/donanım çalıştırılmadı. |
| `KADO-AJANLAR/kado_cekirdek.py` | 1/3 | Mevcut self-test geçiyor; geçici klasörde indeks, karantina, onay akışı, örnek kod onarımı, eklenti ve durdurma davranışı. Gerçek Windows zamanlayıcı/öz onarım doğrulanmadı. AST taraması OS sandbox değildir. |
| `KADO-AJANLAR/kado_19_uzman.py` | 1/3 | 19 benzersiz rol tanımı doğrulandı; görev yürütme testi değildir. |
| `kado_birlesik_motor.py`, `_v2.py`, `_v3.py`, `_v4.py` | 2/3 | V4, V3 alt sürecini ve dosya kuyruğunu izliyor. V4 self-testinde 3 kayıt/durum/sonuç kontrolü geçiyor. Model üretimi denenmedi. |
| `kado_agent_motor/kado_motor.py` | 2/3 | Ollama çağrısı, sınırlı yeniden deneme ve dosya kuyruğu var; `.done` kayıtları gerçek kullanıcı başarısının kanıtı kabul edilmedi. |
| `KADO-AI-COMPANY/.../backend/company/` | 1/3 | 59 güncel pytest testi ve gerçek HTTP/SDK görev denetimi geçti. Sadece mevcut uygulanmış iş akışları; genel amaçlı Windows yürütücü yok. |
| Company `registry.py` | 1/3 | **1 KADO + 4 yönetici + 30 uzman = 35 toplam rol.** Hedef 4 yönetici + 35 uzman tamamlanmış değil. İsim tanımları araç uygulaması değildir. |
| Company `frontend/` | 1/3 | TypeScript ve Vite üretim derlemesi geçti. Gerçek HTTP sunumu test edildi; tarayıcıdaki bütün kullanıcı akışları denenmedi. |
| `kado_bridge/local_host.py` | 2/3 | İncelenmiş ana dosyaya hash kilitli adaptör, araç yönlendirme ve heartbeat var. Kullanıcının Windows kurulumu üzerinde bağlantı yapılmadı. |
| `kado/sistem/whatsapp_kado/` | 2 | WhatsApp Web köprüsü ve worker var. Oturum varlığı güncel hesap bağlantısı kanıtı değil; mesaj gönderilmedi. |
| `kado/sistem/kado_call/`, kök PCM yaması | 2 | Baileys/yerel arama ve PCM kodu var; Windows–WSL/Linux bağımlılıkları incelenmeli. Giden/gelen arama ve gecikme ölçülmedi. |
| `KADO-AJANLAR/kado_influencer_studio.py` | 3 | Kimlik/takvim okuma ve metin taslağı var; yayın kapalı. Video üretimini tamamlamıyor. |
| `KADO_EMINE_KOPRU.py`, `KADO_EMINE_OTOMAT.py` | 2/3 | Emine referansları, TTS/FFmpeg ve isteğe bağlı SadTalker yolları var; medya üretimi bu ortamda çalıştırılmadı. Hareketli fotoğraf, doğrulanmış dudak senkronizasyonu değildir. |
| Ollama/Gemini, ElevenLabs/Piper | 2/3 | Kaynaklarda entegrasyonlar var; güncel servis, anahtar, kota, yerel model ve donanım doğrulanmadı. Company 429/hatalı yanıt testleri sahte HTTP sözleşmesidir. |
| Sosyal platform connector'ları | 5/6 | Company API açıkça unavailable döndürüyor; resmî OAuth/yayın adaptörleri tamamlanmamış. |
| `kado-agent.mjs`, `kado-config.json`, `kado-hafiza.json`, Nexus `localhost:4141` | 5 | Bu adlarla bağımsız hedef kaynaklar bulunamadı; benzer köprüler onların çalıştığı şeklinde yorumlanmadı. |
| Eski/çift başlatıcılar ve `yedek_20261111/`, `yukle/` | 7/2 | Tarihsel kopyalar korunuyor. Aynı anda çalıştırılmaları merkezî tek kuyruk anlamına gelmez. Hiçbiri otomatik silinmedi. |
| `KADO-AJANLAR/tests/kado_notifier_test_patch.py` | 4/2 | Bağımsız Python dosyası olarak satır 1'de IndentationError; muhtemel sınıf içi yama parçası. Çalışan uygulamaya rastgele eklenmedi. |
| Yeni Company yedekleme/geri yükleme | 1/3 | WAL hafızası, kanıt dosyaları, bozuk arşiv/yol kaçışı/aygıt adları ve mevcut hedef koruması test edildi. Windows başlatıcıları henüz cihazda denenmedi. |

## Mimari kararı

Mevcut Company API/SQL görev motoru ve denetim zinciri bütünleştirme merkezi olarak korunuyor. Eski sesli KADO kullanıcı kimliğini ve ses motorunu korur; `kado_bridge` üzerinden iş iletir. Eski dosya kuyrukları şimdilik tarihsel/bağımsızdır. Hepsini aynı anda başlatan bir betik eklenmedi: bu, çifte görev ve çelişen başarı raporu üretebilir.

`KADO_BASLAT.bat` yalnızca Company motoru/paneli açar. Sesli KADO, WhatsApp ve Emine'nin bağlı olduğunu göstermez. Yeni kök kısayollar mevcut kurulum ve sahiplik denetimini kullanır. Ses ID'leri, oturumlar, eski ayarlar ve görseller değiştirilmedi.

## Bu değişiklikte tamamlanan işler

- Kök giriş ve kapsam belgesi; mevcut kurulum/başlat/durdur/test dosyalarına yönlendirme.
- Salt okunur envantere Python AST sözdizimi kanıtı ve açık `runtime_status=unverified` bilgisi.
- Company verileri için SQLite backup API ile WAL tutarlı yedek, dosya SHA-256 manifesti ve bütünlük denetimli yeni klasöre geri yükleme.
- Gizli token/log/oturum verilerinin yeni yedek kapsamından çıkarılması; boyut/dosya sayısı sınırları ve Windows yol denetimleri.
- Kaynak paketleyicide eski manifestin ikinci kez ZIP'e eklenmesi düzeltildi; benzersiz arşiv girdileri ve bütün dosya hash’leri tekrar doğrulanıyor.
- Gelecekte oturum/arşivlerin eklenmesini önleyen ignore kuralları. **Ignore kuralı geçmişte commit edilmiş oturumları depodan veya geçmişten çıkarmaz.** Depo herkese açık; 65 izlenen tarayıcı oturum yolu mevcut. Kullanıcı bu oturumları gözden geçirmeli ve aktifse iptal etmelidir. Geçmiş yeniden yazılmadı ve veri silinmedi.

## Güncel doğrulama

Ortam Linux, Python 3.12.14, Node.js 24.22.1. Çekirdek: `python -m pytest -q` → **59 geçti**, bir bağımlılık deprecation uyarısı. Panel: `npm --prefix frontend run build` → başarılı. `scripts/live_smoke_test.py` → gerçek yerel HTTP, SDK, tekrar gönderim engeli, dosya hash kanıtı, denetçi kabulü ve yeniden başlatmada geçmiş koruması geçti. `kado_cekirdek.py selftest`, V4 `selftest` ve 19 rol doğrulaması başarılı. Testler dış hesaplara mesaj/yayın göndermedi.

## Kalan kabul koşulları — kapsam korunuyor

1. **Kurtarma:** kullanıcının gerçek SQLite hafızası, eski `.env`/ses ayarları ve depoda bulunmayan ZIP/model varlıkları için yerel, gizli veri dışa aktarmayan karşılaştırma ve ayrı yedek.
2. **Mimari/ajanlar:** dört yönetici + 35 uzman hedefi ile mevcut 19 ve 30 uzman haritalaması; her uzman için gerçek araç ve izin kanıtı. 87 kopya grubunun hangi sürümünün aktif olduğunun Windows süreçlerinden doğrulanması.
3. **Windows:** araçların izinli proje alanı, süre/kaynak sınırı ve güvenli süreç sahipliğiyle bağlanması. Üretim komutları için OS izolasyonu.
4. **Ses/WhatsApp:** kullanıcı makinesinde mikrofon, TTS, söz kesme, metin/ses aktarımı, ayrı gelen/giden arama ve gecikme testleri; resmî API ile kişisel köprünün ayrılması.
5. **Medya/sosyal:** Emine hattının gerçek ses/video çıktısı, FFprobe kalite kanıtı, model lisansları/CPU uygunluğu, altyazı/dudak senkronu; resmî OAuth, yayın kuyruğu ve platform izinleri.
6. **Hafıza/projeler:** eski hafızanın açık eşlemesi, anlamsal arama, HAN TOYS/SAHACEP alan izolasyonu, harici çalışma alanlarının ayrı yedeği.
7. **Otonomi/onarım:** birleşik kalıcı zamanlayıcı, gerçek bütçeler, yeni uzman oluşturma ve iptal sınırları; onaylı kod dalı/test/geri dönüş dağıtım akışı. Genel `KADO_ONAR.bat` henüz yok; mevcut self-test geçişi genel üretim onarımı olarak sunulmuyor.
8. **Arayüz/teslimat:** istenen 18 panel alanının her birinin çalışan araçlarla eşlemesi, tarayıcı akışları, Windows tek başlatmanın bütün servislerle cihaz testi ve son kabul raporu.

Bu kabul koşulları sağlanmadan “üretime hazır Windows AI işletim sistemi tamamlandı” sonucu çıkarılamaz.
