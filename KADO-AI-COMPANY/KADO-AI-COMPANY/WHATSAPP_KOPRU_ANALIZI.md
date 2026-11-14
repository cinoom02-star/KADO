# Mevcut WhatsApp köprüsünün inceleme durumu

**Bu ortamda mevcut köprü kodu, Windows dosyaları veya gerçek WhatsApp hesabı bulunmamaktadır. Mevcut köprü incelenmiş veya bağlanmış değildir.** Yeni pakette mevcut taşıyıcıyı koruyan adaptör sözleşmeleri ve yerel sözleşme testleri bulunur; bunlar gerçek hesap testi yerine geçmez.

## Kullanıcının bildirdiği önceki çalışma

Chromium / Puppeteer tabanlı WhatsApp Web oturumu QR ile bağlanmış; metin alma / cevaplama denenmiş; gelen sesli mesajın KADO tarafından işlenip metin yanıtı üretmesi test edilmiş. Gemini tarafında 429 kota ve bazı mesaj kimliği hataları görülmüş. Node.js / `baileys-caller` yaklaşımıyla 16 kHz mono PCM, Float32 → Int16, tamponlama, sessizlik ve barge-in üzerine çalışma yapılmış. Gerçek arama denemelerinde iyileşme bildirilmiş; 2–3 saniye gecikme hedefi kesin ölçülmemiş.

Bu maddeler kullanıcının geçmiş çalışma kaydıdır. Bu teslimatta bağımsız doğrulama yapılmadığından hiçbiri otomatik olarak bugünkü çalışan yetenek listesine aktarılmaz.

## Kod geldikten sonra salt okunur analiz

1. `scripts/inspect_existing_kado.py` ile mevcut iki klasörün sınırlı envanterini çıkarın. Oturum / anahtar dosyalarını paylaşmayın.
2. Gerçek çalışan başlatıcıyı ve taşıyıcı sürümünü belirleyin. `BASLAT.bat`, `WHATSAPP_BASLAT.bat` ve `KADO_BIRLESIK_BASLAT.bat` adları çalışma kanıtı değildir.
3. Olay dinleyicilerini ve mesaj kimliği / gönderen kimliği dönüşümünü eşleyin. Hata durumunda kimliksiz veya iki kez işlenen mesaj oluşup oluşmadığını kontrol edin.
4. Gönderim sonucunun gerçek teslim kimliğini ve belirsiz teslim durumunu nasıl bildirdiğini inceleyin. 429 için gecikme ve sınırlı yeniden deneme davranışını ölçün.
5. Ses çözümleme, STT, ElevenLabs / yerel TTS ve mevcut ses kimliğinin giriş / çıkış formatını doğrulayın.
6. Giden / gelen çağrı, cevaplanma, PCM gönderme ve PCM alma için ayrı giriş noktaları ve kanıtları bulun. Kütüphane adından destek varsaymayın.
7. Mevcut dosya değişikliği gerekiyorsa yedek ve somut değişiklik planı hazırlayın. Mevcut oturumu veya ses ayarlarını yeniden oluşturmayın.

## Bu paketin sağladığı bağlantı sınırı

| Parça | Bu teslimat | Gerçek doğrulama gereği |
| --- | --- | --- |
| Sahip kimliği ve komut öneki | Adaptör kontrolü | Taşımanın güvenilir gönderen alanına eşlenmeli |
| Yinelenen gelen mesaj | Kalıcı SQLite günlük / idempotency | Gerçek tekrar teslim testi |
| Görev atama | Merkezî SDK görev kuyruğu | Eski KADO komut noktasına bağlanmalı |
| Giden metin | Taşıma protokolü ve kalıcı outbox | Hesap üzerinden alıcı teslimi |
| Sesli mesaj | Açık sağlayıcı / taşıma sözleşmesi | STT, TTS ve gerçek sesli gönderim |
| Giden / gelen arama | Destek ve kanıt kontrolü, ayrı durumlar | Mevcut arama motoru ve gerçek taraf |
| Çift yönlü konuşma | PCM yardımcıları ve açık sözleşme | İki yön ses, gecikme, barge-in |

Yeni WhatsApp taşıması, yeni QR oturumu veya resmî API'de olmayan arama yeteneği uydurulmamıştır. Mevcut Puppeteer / Baileys tabanlı yaklaşımın çalışması sürüme ve oturuma bağlıdır; desteklenmeyen yetenek engellenir ve hata olarak raporlanır.

## Doldurulacak saha kaydı

Windows tarihi / saat dilimi, köprü sürümü / commit'i, test hesabı için maskelenmiş tanım, desteklenen yetenek, gerçek görev / mesaj / arama kimliği, hata kodu, deneme sayısı ve kanıt yolu kaydedilmelidir. API anahtarı, QR, oturum dosyası veya konuşma içeriği gereksiz yere kayda alınmamalıdır. Gerçek hesap denemeleri için [WHATSAPP_ARAMA_TESTLERI.md](WHATSAPP_ARAMA_TESTLERI.md) kullanılır.
