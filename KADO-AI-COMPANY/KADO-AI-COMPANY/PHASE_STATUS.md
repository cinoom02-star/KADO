# Aşama ve kapsam durumu

Bu paket bir **ilk çekirdek teslimatıdır**. Aşağıdaki "uygulandı" sözcüğü kaynak kodundaki bileşeni belirtir; test kanıtı [TEST_SONUCLARI.md](TEST_SONUCLARI.md) içinde ayrı verilir. Gerçek KADO / WhatsApp bağlantısı yapılmadığı için tüm kabul koşulları karşılanmış değildir.

| Aşama | İlk teslimattaki kapsam | Kalan işler |
| --- | --- | --- |
| 1 — Çekirdek | FastAPI, kalıcı SQL görev kuyruğu, 35 rol, yerel panel, SQLite varsayılanı | Gerçek Windows çalıştırması; kullanıcı makinesinde PostgreSQL yapılandırması |
| 2 — Araç ve denetim | Gerçek dosya envanteri / hash kanıtı, yönetici–uzman aktarımı, bağımsız denetim, sınırlı yeniden deneme, olay / araç günlüğü | Bütün uzman iş akışları; bağımsız kanıt kaynaklı gelişmiş tartışma; genel kod sandbox'ı |
| 3 — KADO ve Windows | Bağımsız REST / Python SDK / CLI / WebSocket, Windows kurulum–başlatma–durdurma dosyaları, salt okunur inceleme aracı | Mevcut KADO giriş noktasına gerçek adaptör eşlemesi; gerçek Windows denemesi |
| 4 — Sosyal ve medya | Connector durumları ve desteklenmeyen yeteneklerin açık gösterimi; WhatsApp / ses taşıma sözleşmeleri | Hesap OAuth, resmî API paylaşımı, mevcut WhatsApp / ses motoru, aramalar, Emine üretim hattı |
| 5 — Geniş iş akışları | Gerçek dosya görevi ve yapılandırılabilir Ollama / Gemini görev sağlayıcıları | Kod üretim / test sandbox'ı, kaynaklı internet araştırması, e-ticaret, film / video üretimi |
| 6 — Sertleştirme | Token, dosya kapsamı, rol izinleri, kalıcı olaylar, kontrollü eşzamanlılık, kill switch | OS sandbox, TLS / çok kullanıcı RBAC, dağıtık işçi liderliği, ölçülmüş performans, otomatik güvenli yedek / geri yükleme, kapsamlı maliyet bütçeleri |

35 rolün tanımlanması 35 uzmanın bütün yeteneklerinin tamamlanması değildir. Model sağlayıcısı ayarlı değilken içerik üretildiği, connector bağlanmadan yayın yapıldığı veya mevcut taşıma test edilmeden arama gerçekleştiği iddia edilmez.

## Kullanıcının 15 çekirdek test ölçütünün eşlemesi

| # | Ölçüt | Doğrulama yolu |
| --- | --- | --- |
| 1 | Backend başlama | API testleri ve gerçek uvicorn sağlık isteği |
| 2 | Panel–backend bağlantısı | Üretim derlemesi ve statik HTTP sunumu geçti; tarayıcı etkileşimi test edilmedi |
| 3 | Veritabanı | SQLite kalıcılık / tekrar açma; PostgreSQL ayrıca |
| 4 | Ajan görev alma | Gerçek `workspace_audit` |
| 5 | Ajanlar arası aktarım | Görev olayları ve rol kimlikleri |
| 6 | Yönetici–uzman atama | Atama olayları ve araç kaydı |
| 7 | Hatalı çıktı reddi | Değiştirilmiş kanıtla bağımsız denetim testi |
| 8 | Yeniden işleme | Red / yeniden deneme sayacı testi |
| 9 | API hataları | Sağlayıcı ve SDK hata / 429 sözleşme testleri |
| 10 | Yeniden başlatmada geçmiş | Aynı veritabanını yeni Store ile açma |
| 11 | İzinler | Yetkisiz API, rol, yol dışına kaçış ve sembolik bağlantı testleri |
| 12 | KADO adaptörü | SDK sözleşmesi ve `KADO_BAGLANTI_TESTI.py`; eski KADO ayrıca |
| 13 | Connector doğruluğu | Yapılandırılmamış / desteklenmeyen durumların API kontrolü |
| 14 | Gerçek araç günlüğü | Araç kaydı ile dosya kanıtının eşlemesi |
| 15 | Uzun görev iptali | İşçi kontrol noktası / iptal testi; gerçek dış taşıma ayrıca |

Kesin komut, geçen / kalan test sayısı ve çalışma ortamı son test raporuna işlenir. Burada yöntem listelenmesi bir testin geçtiğini göstermez. Gerçek KADO, Windows, WhatsApp metin / ses, gelen / giden arama, çift yönlü ses ve gecikme saha testleri **yapılmamıştır**.
