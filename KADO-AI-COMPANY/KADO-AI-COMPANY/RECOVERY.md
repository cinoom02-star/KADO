# KADO veri kurtarma

Bu araç **AI Company verilerini** korur; eski `kado/` ve `KADO-AJANLAR/` hafızasını, WhatsApp oturumlarını veya hesap anahtarlarını otomatik taşımaz. Tüm KADO'nun yedeği değildir.

1. Backend'i `DURDUR.bat` ile kapatın. Aynı veriyi kullanan diğer süreçler de kapalı olmalı. Süreç sahiplik kaydı varsa yedekleme reddedilir; PID dosyasını körlemesine silmeyin.
2. `KADO_YEDEKLE.bat` SQLite anlık kopyasını ve veri dosyalarını `backups/kado-TARIH.zip` içine yazar. Dosya sayısı/boyutu sınırlıdır. Var olan bir yedek değiştirilmez. Kaynak veri silinmez.
3. `KADO_GERI_YUKLE.bat "C:\Yedek\kado.zip" "C:\KADO\kurtarilan-veri"` çalıştırın. Hedef klasör önceden mevcut olmamalı. Manifest, hash, boyut, yol kapsamı ve SQLite bütünlüğü yazmadan önce denetlenir.
4. Yeni klasörü `KADO_DATA_DIR` olarak yapılandırın. Harici `KADO_WORKSPACE_ROOT` kullanıldıysa o çalışma alanını ayrıca yedekleyin. `.env`, API token ve bağlantı ayarları bu yedeğe dahil değildir. Yeni token veya açıkça yapılandırılmış `KADO_API_TOKEN` kullanın. Eski tokenla istemcileri otomatik bağlamayın.

Geri yükleme bir doğrulanmış arşivden veri kopyalar; görevlerin içindeki tarihsel mutlak dosya yollarını yeniden yazmaz. Eski kanıt kayıtları eski yolları gösterebilir. Yeniden başlatmada yarım görevler mevcut kuyruğun kurtarma kurallarına tabidir.

Yedekler **şifrelenmez** ve hafıza/görev metinleri içerebilir; kendi erişimi kısıtlı yerel diskinizde saklayın. Hash denetimi bozulmayı yakalar; güvenilmeyen birinin değiştirdiği manifesti doğrulayacak dijital imza değildir. Yalnızca kendi yedeklerinizi kullanın.

Özel `DATABASE_URL` Windows kısayolunda açıkça reddedilir. PostgreSQL için `pg_dump`/`pg_restore` kullanın. Geliştirici CLI'si `python -m company.recovery backup --data-dir ... --destination ...` (PYTHONPATH=backend) yalnızca açıkça seçilen veri klasörünü kapsar; harici veritabanını bulduğunu iddia etmez.

Linux otomatik testleri WAL içindeki kalıcı hafızayı, çıktı dosyalarını, değiştirilmiş arşiv reddini, yol kaçışı ve Windows aygıt adı reddini, var olan hedefin korunmasını doğrular. `.bat` dosyaları gerçek Windows üzerinde henüz denenmedi.
