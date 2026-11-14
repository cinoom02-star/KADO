# Mevcut KADO'ya bağlantı rehberi

Bu teslimat KADO'nun gerçek kaynaklarını içermez. `C:\KADO\kado` ve `C:\KADO\KADO-AJANLAR` içindeki giriş noktaları, WhatsApp taşıması, ElevenLabs kimliği ve hafıza API'si tahmin edilmemiştir. Gerçek Windows bağlantısı bu ortamda test edilmemiştir.

## 1. Ayrı kurulum ve salt okunur inceleme

Paketi `C:\KADO\KADO-AI-COMPANY` gibi ayrı bir klasörde kurun ve başlatın. KADO'nun çalışan oturumunu koruyun. Salt okunur envanter için bu projenin terminalinden çalıştırın:

```powershell
.venv\Scripts\python.exe scripts\inspect_existing_kado.py "C:\KADO\kado" "C:\KADO\KADO-AJANLAR" > data\kado-inventory.json
```

İnceleyici gizli anahtar ve oturum dosyalarını atlar. Rapor bir çalışma kanıtı değil, adaptör eşlemesi için dosya / imza envanteridir. Raporu paylaşmadan önce özel bilgi açısından kontrol edin. Dosya adından WhatsApp araması veya ses desteği var sonucu çıkarılmaz.

Gerçek giriş fonksiyonunu, olay biçimini, gönderen kimliği alanını, mesaj kimliğini, ses formatını ve hata kodlarını mevcut kod üzerinden belirleyin. Değişiklik gerekirse önce mevcut proje ve oturumların uygun yedeğini alın; değişiklik planını kullanıcıya gösterin. Bu paket bu değişikliği otomatik uygulamaz.

## 2. Bu servisin gerçek bağlantı testi

```powershell
.venv\Scripts\python.exe KADO_BAGLANTI_TESTI.py --url http://127.0.0.1:8765 --token-file data\api-token.txt
```

Bu komut SDK ile backend arasında gerçek görev alışverişini kontrol eder. Testin geçmesi eski KADO sürecinin, WhatsApp hesabının veya sesli aramanın bağlandığı anlamına gelmez. Ortam değişkeniyle token verdiyseniz güvenli bir yerel token dosyası veya test aracının desteklediği yapılandırmayı kullanın; token'ı komut geçmişine yazmayın.

## 3. Python tarafından görev verme

Mevcut KADO kodunu düzenlemeden önce ayrı bir deneme dosyasında SDK'yı çalıştırın. İmza ve giriş noktasını mevcut KADO'nun gerçek koduna göre eşleyin:

```python
from pathlib import Path
from kado_bridge import KadoClient, KadoTaskDispatcher

token = Path("data/api-token.txt").read_text(encoding="utf-8").strip()
with KadoClient("http://127.0.0.1:8765", token) as client:
    task = client.create_task(
        "KADO deneme denetimi",
        kind="workspace_audit",
        input={"path": "."},
        idempotency_key="yerel-deneme-001",
    )
    result = KadoTaskDispatcher(client).wait(task["id"])
    print(result["status"], result.get("result"))
```

Aynı `idempotency_key` aynı işi yeniden göndermemek içindir; her yeni komut için benzersiz kimlik kullanın. Gerçek WhatsApp komutunda bu kimlik güvenilir taşımanın mesaj kimliğinden türetilmelidir.

Köprü modülleri: `kado_adapter.py`, `kado_agent_gateway.py`, `kado_event_bus.py`, `kado_task_dispatcher.py`, `kado_whatsapp_adapter.py`, `kado_voice_adapter.py`, `kado_memory_adapter.py` ve `kado_health_monitor.py`. Kalıcı görev asıl backend kuyruğundadır; KADO bağlantısı kesilse de görev kimliğiyle durum yeniden sorgulanabilir.

CLI örnekleri:

```powershell
.venv\Scripts\python.exe -m kado_bridge --token-file data\api-token.txt health
.venv\Scripts\python.exe -m kado_bridge --token-file data\api-token.txt submit "Calisma alani denetimi" --wait
.venv\Scripts\python.exe -m kado_bridge --token-file data\api-token.txt status GOREV_KIMLIGI
```

WebSocket yolu `/api/ws/events`'tir. İlk JSON mesajı `{ "token": "YEREL_TOKEN", "after": 0 }` biçiminde kimlik doğrular. Token URL sorgusunda taşınmaz. İstemci aldığı en son olay kimliğini tutup yeniden bağlandığında `after` imlecini ilerletir. LocalEventBus yalnızca aynı Python sürecinde çalışır.

## 4. Mevcut WhatsApp ve ses motorunu bağlama

`KadoWhatsAppAdapter` yeni WhatsApp hesabı veya QR oturumu açmaz. Mevcut taşımanın `capabilities()` ve ilgili gönderim / arama sözleşmelerini açık bir sarmalayıcıyla uygulaması gerekir. Desteklenen ve gerçekten doğrulanan yetenekler ayrı alanlardır. Kaynak bağlantısı olmayan taşıma özellikleri engellenir.

`receive_text(message_id, sender, text, dispatch)` çağrısında izinli sahip kimliği ve komut öneki kontrol edilir. `dispatch(command, idempotency_key)` merkezî SDK kuyruğuna gönderir. Aynı mesaj kimliği kalıcı günlükle yinelenmez. Sonuç KADO tarafından oluşturulup `queue_reply` ve `deliver_reply` yoluyla mevcut taşıma üzerinden gönderilir. Teslimi belirsiz sonuçlar yeniden göndermeden önce taşımanın gerçek mesaj geçmişiyle uzlaştırılır.

Bağlantı yeniden geldiğinde `retry_pending(dispatch)` aynı merkezî idempotency anahtarıyla bekleyen komutları yeniden dener. `collect_completed(client, render_result)` tamamlanan gerçek görevi alır; `render_result` mevcut KADO'nun son yanıtını oluşturan geri çağrıdır. Dönen outbox anahtarları `deliver_reply` ile gönderilir. `UNKNOWN` / yarıda kalmış gönderimlerde `reconcile_reply` gerçek taşıma kanıtıyla çalıştırılmalıdır. Yerel WhatsApp günlüğü komut / konuşma içeriği içerebilir; `data/` klasörünü kullanıcıya özel tutun.

Ses adaptörü mevcut STT, ElevenLabs veya yerel TTS sağlayıcısını sözleşmeyle bağlar. 16 kHz mono PCM dönüşümü ve tampon araçları gerçek ses aktarımının yalnızca bir parçasıdır. Ses kimliği, STT doğruluğu, karşı tarafın duyduğu ses ve gecikme Windows'ta ayrı test edilir. Çalışan ElevenLabs ayarlarını taşımak veya değiştirmek gerekmez.

Aramalar için ayrıntılı ve ayrı doğrulama adımları: [WHATSAPP_ARAMA_TESTLERI.md](WHATSAPP_ARAMA_TESTLERI.md). Taşıma yeteneği eksikse arama başarısı bildirilmez.

## 5. Kabul ve geri dönüş

Önce bağımsız SDK testi, ardından KADO'nun yalnızca deneme komutu, sonra sahip kimlikli WhatsApp metni, sesli mesaj ve en son açık izinli arama denenir. Her aşamada gerçek görev / mesaj / arama kimliği, durum, hata ve kanıt kaydedilir. Hata olursa KADO adaptörünü devre dışı bırakın; bu bağımsız servisi `DURDUR.bat` ile kapatın. Mevcut KADO kurulumu değiştirilmediyse eski başlatma düzeni kullanılmaya devam eder.
