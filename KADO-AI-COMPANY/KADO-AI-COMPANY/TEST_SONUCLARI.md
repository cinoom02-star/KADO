# Doğrulama raporu — 13 Kasım 2026

Bu rapor ilk çalışan çekirdeğin kapsamını gösterir. Tam 35 uzmanlık iş akışının ve gerçek Windows KADO / WhatsApp bağlantısının tamamlandığı iddiası değildir.

## Gerçek ortam ve sonuçlar

Linux yönetilen geliştirme ortamında Python 3.12.14, Node.js 24.22.1, React 19, FastAPI, SQLAlchemy ve PostgreSQL 16 kullanıldı.

| Kontrol | Sonuç | Kanıt |
| --- | --- | --- |
| Python API / görev motoru / saklama / köprü testleri | **43 geçti** | `verification/pytest.txt`; `tests/` |
| TypeScript kontrolü | **Geçti** | `npm --prefix frontend run check` |
| React/Vite üretim derlemesi | **Geçti** | `frontend/dist/` |
| Gerçek uvicorn HTTP + KADO Python SDK + SQLite | **Geçti** | `verification/sqlite/verification.json` |
| Gerçek uvicorn HTTP + SDK + PostgreSQL 16 | **Geçti** | `verification/postgres/verification.json` |
| API üzerinden 35 rolün okunması | **Geçti** | Her iki gerçek HTTP testi |
| Gerçek dosya, uzman araç çağrısı, QA ve denetçi | **Geçti** | `report.json`, `qa.json`, `audit.json`, `tool-calls.json` |
| Aynı isteğin iki kez görev oluşturmaması | **Geçti** | Gerçek HTTP testinde aynı anahtar / aynı görev kimliği |
| Backend sürecinin kapanıp yeniden başlamasında geçmiş | **Geçti** | Her iki veritabanında aynı sonuç ve olaylar geri okundu |
| Derlenmiş panelin backend tarafından HTTP sunumu | **Geçti** | Gerçek HTTP `/` yanıtı |
| Tarayıcıda panel etkileşimi / görüntü testi | **Test edilmedi** | Bu oturumda gereken `cua_repl.js` tarayıcı aracı mevcut değildi |
| Gerçek Windows BAT / PowerShell çalıştırma | **Test edilmedi** | Windows 10/11 saha testi gerekli |
| Kullanıcının mevcut KADO sürecine bağlantı | **Test edilmedi** | Kaynaklar ve Windows makinesi bu ortamda yok |
| Gerçek WhatsApp metin / ses / gelen ve giden arama | **Test edilmedi** | Mevcut taşıma motoru ve hesap gerekli |
| Canlı Ollama / Gemini / ElevenLabs / Piper | **Test edilmedi** | Model, anahtar ve yerel ses motoru bağlanmadı |
| Sosyal API yayını, Emine video üretimi | **Uygulanmadı** | Durumları açıkça `unavailable`; yayınlama başarısı üretilmez |

Python testinde tek bir üçüncü taraf Starlette / AnyIO kullanım dışı kalma uyarısı görüldü; başarısız test yoktu.

## Uçtan uca yapılan gerçek iş

1. Yalıtılmış geçici çalışma alanında `proof.txt` oluşturuldu.
2. Gerçek HTTP sunucusu başlatıldı; SDK kimlik doğrulayarak görev gönderdi.
3. KADO rolü işi CTO'ya, CTO uzman dosya aracına aktardı.
4. Uzman gerçek dosyayı okuyup SHA-256 ve boyut raporu yazdı.
5. QA ve Quality Auditor dosyaları ayrı ayrı yeniden okuyarak kanıtı doğruladı.
6. Görev `APPROVED` oldu; gerçek araç ve atama olayları kalıcı veritabanına yazıldı.
7. Sunucu kapatılıp açıldı; görev sonucu ve geçmiş tekrar okundu.

İki veritabanı denemesinde de **21 gerçek olay** kaydedildi. Görevlerin kimlikleri ve rapor hash'leri ilgili `verification.json` dosyasındadır. `proof.txt` ve üretilmiş kanıtlar pakette bulunur. Kanıtlardaki geçici dosya yolları test anındaki yolları gösterir; kullanıcı makinesinde mevcut yol oldukları iddia edilmez.

Bozuk kanıt testi rapor dosyasının hash'ini bilinçli değiştirir: QA reddeder, revizyon kaydı oluşur ve yeniden üretilen gerçek dosya kanıtı onaylanır. İptal testi sürmekte olan bir aracı durdurup aynı işçinin sonraki gerçek görevi bitirebildiğini doğrular. Zaman aşımı ve genel durdurma ayrıca sınanır.

WhatsApp / ses testleri açıkça test taşıyıcılarıyla yapılan **sözleşme testleridir**: gönderen yetkisi, kalıcı çift işleme önleme, belirsiz teslimde yeniden göndermeme, yeniden bağlantı, arama yetenek kapısı, AI tanıtımı, PCM dönüşümü ve alternatif sağlayıcı davranışı. Gerçek hesap başarısı sayılmaz. Ollama / Gemini HTTP 429 ve hata gizleme denemeleri de HTTP test taşıyıcısı kullanır.

## Tekrar çalıştırma

```text
python -m pytest -q
npm --prefix frontend run check
npm --prefix frontend run build
python scripts/live_smoke_test.py --output verification/sqlite
```

İsteğe bağlı gerçek PostgreSQL doğrulaması Docker ve `postgres:16-alpine` gerektirir. `python scripts/live_smoke_test.py --postgres --output verification/postgres` geçici bir PostgreSQL konteyneri başlatır, yalnızca loopback'e geçici port açar, rastgele parola kullanır ve sonunda konteyneri siler. Windows Docker Desktop'ta betiğin sabit Linux Docker soketini uyarlamak gerekir; bu özel otomatik test Windows'ta denenmedi.

Windows'ta çekirdek testler için `TEST_ET.bat`, çalışan sidecar SDK testi için `KADO_BAGLANTI_TESTI.py`, mevcut kaynakları salt okunur incelemek için `scripts/inspect_existing_kado.py` kullanılır. Gerçek WhatsApp ve arama kabul adımları `WHATSAPP_ARAMA_TESTLERI.md` içindedir.
