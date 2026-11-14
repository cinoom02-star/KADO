# Güvenlik ve yetkiler

Servis varsayılan olarak yalnızca `127.0.0.1:8765` üzerinde dinler. Yerel panel ve API bearer token kullanır. Token ortamda verilmezse yerel veri klasörüne üretilir. Sağlık uç noktasının erişilebilir olması görev API'sine yetki vermez. Token'ı ekran görüntüsü, kaynak paketi veya hata raporuyla paylaşmayın.

## Dosya ve araç kapsamı

İş araçları yapılandırılmış çalışma alanında çalışır. Kök dışına yol geçişi ve sembolik bağlantıyla kaçış reddedilir. Hassas dosya adları ve oturum verileri iş envanterine alınmamalıdır. Yeni araçlar için rol izni zorunludur. İlk sürüm genel kabuk / terminal komutu veya kullanıcı kodu çalıştırmaz; işletim sistemi düzeyinde keyfi kod sandbox'ı sağlandığı iddia edilmez.

Mevcut KADO ve WhatsApp kaynakları salt okunur inceleme aşaması dışında otomatik açılmaz veya değiştirilmez. `scripts/inspect_existing_kado.py` anahtar ve oturum dosyalarını atlar; çıktıyı yine de paylaşmadan önce inceleyin. Kaynak kod parçaları özel bilgi taşıyabilir.

## Onay ve mesaj kimliği

Dosya silme, canlı dağıtım, ödeme, satın alma, hesap yetkisi değişikliği, yayınlama ve geri alınması güç dış eylemler kullanıcı onayı gerektirir. İlk sürümde onay kuyruğunun bulunması bu dış araçların tamamlandığı anlamına gelmez. Bir connector'a gerçek uygulama eklendiğinde onay kimliği tek işlem kapsamına bağlanmalıdır.

WhatsApp gönderen kimliği, izinli sahip listesi ve komut biçimi birlikte doğrulanır. Sıradan gelen mesaj görev yönetme yetkisi kazanmaz. Mesaj kimlikleri yinelenen görevleri önlemek üzere kalıcı tutulur. Taşıma katmanı, gerçek WhatsApp olayını ve gönderen kimliğini güvenilir biçimde eşlemelidir. Kullanıcı metninden yetki çıkarılmaz.

Aramalarda KADO yapay zekâ asistanı olduğunu belirtir. Görüşme kaydı ve ses saklama ayrı izin gerektirir; bu paket varsayılan bir görüşme kaydedicisi açmaz. Arama, yanıtlanma, ses gönderme ve ses alma ayrı ayrı doğrulanır.

## Gizli bilgiler ve sağlayıcılar

`.env`, `data/`, kimlik doğrulama oturumları ve günlükler kaynak depodan dışlanır. Örnek yapılandırma gerçek anahtar içermez. Bu ilk sürüm işletim sistemi gizli bilgi kasasının yerini almaz; dosya erişimini Windows kullanıcı izinleriyle sınırlandırın. Gemini'ye yalnızca göndermeyi kabul ettiğiniz görev içeriğini iletin. Ollama gibi yerel sağlayıcıların uç noktalarını da açık internete yayınlamayın.

Haricî belgeler, web sayfaları, model yanıtları ve WhatsApp metinleri güvenilmeyen girdidir. Bunlar araç iznini genişletemez, onayı atlayamaz veya sistem yapılandırmasını değiştiremez. Bu yaklaşım bütün prompt injection saldırılarının çözüldüğü garantisi değildir; yeni araçlar aynı sınırları uygulamalıdır.

## İşletim sınırları

Genel durdurma anahtarı yeni işleri durdurur ve çalışan işler kontrol noktalarında durur. Ağ çağrısı için zaman aşımı vardır; daha önce dış sisteme iletilmiş bir eylemi geri alamaz. Süreç kapatılırsa görevler kalıcı kayıtlardan yeniden değerlendirilir. Yalnızca bu paketin PID kaydı doğrulanarak durdurulur; bütün Python veya Node süreçleri topluca kapatılmaz.

Token / API kullanım kayıtları gerçek yanıt verisine dayanmalıdır; fiyat bilgisi olmayan sağlayıcı için kesin para maliyeti uydurulmamalıdır. İlk sürüm genel bulut fatura limiti uygulamaz; sağlayıcı tarafı kotaları ve dar görev sınırları kullanılmalıdır.

Yerel kullanım önceliklidir. TLS, çok kullanıcılı RBAC, ağ üzerinden üretim yayını, dağıtık kuyruk, dosya şifrelemesi ve işletim sistemi izolasyonu için ek üretim sertleştirmesi gerekir. Bkz. [PHASE_STATUS.md](PHASE_STATUS.md).
