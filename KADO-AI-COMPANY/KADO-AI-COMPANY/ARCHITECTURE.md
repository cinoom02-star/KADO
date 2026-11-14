# KADO AI Company mimarisi

Bu belge ilk teslimatın mimarisini tanımlar. Şirket sahibi kullanıcı, CEO mevcut KADO'dur. Bu paket ayrı bir görev işletim katmanıdır; KADO'nun kimliğini, hafızasını veya konuşma motorunu devralmaz.

```text
Mevcut KADO / yetkili Windows kullanıcısı
   │ REST SDK, WebSocket olay akışı, Python adaptörü / CLI
   ▼
FastAPI + kimlik doğrulama + görev / onay API'si
   │
   ├── kalıcı görev kuyruğu → sınırlı eşzamanlı yürütücüler
   │     └── yönetici → uzman → araç kanıtı → bağımsız denetçi
   ├── görevler, olaylar, araç çağrıları, hafıza, onaylar
   │     └── SQLAlchemy → SQLite; isteğe bağlı PostgreSQL
   └── React paneli: yalnızca gerçek API verileri

KADO köprüsü → mevcut WhatsApp / ses taşıması
                └── açık yetenek bildirimi ve ayrı gerçek bağlantı testleri gerekir
```

## Neden bu seçimler?

Python 3.12 ve FastAPI mevcut Python KADO ile bağlanmayı kolaylaştırır. React, TypeScript ve Vite paneli bağımsız kaynak koduyla üretir; derlenmiş paneli aynı FastAPI süreci sunar. Çalışma zamanında geliştirme platformu veya Sites barındırması gerekmez.

SQLAlchemy, küçük yerel kurulumda ek servis gerektirmeyen SQLite ve daha sonra PostgreSQL kullanımını destekler. Kuyruk veritabanında kalıcıdır; Redis zorunlu değildir. İlk sürüm tek uygulama süreci içindir; çoklu sunucu dağıtımı, lider seçimi ve ayrı dağıtık işçi kümeleri doğrulanmamıştır. `uvicorn --workers` sayısını artırmayın.

Hafıza alanları ajan, şirket, proje ve görev kapsamlarıyla ayrılır. İlk teslimat ilişkisel kayıt sağlar; vektör arama / Qdrant / Chroma entegrasyonu henüz yoktur. Bu özellik arayüzde varmış gibi sunulmamalıdır.

35 ajan 35 ayrı model değildir. Kayıt defteri 1 mevcut CEO bağlantısını, 4 yöneticiyi ve 30 uzman rolünü tanımlar. Bir görev yalnızca ihtiyaç duyduğu rol ve izinlerle çalışır. Yapılandırılmamış model sağlayıcısı gerçek çağrı yapılmış gibi görünmez. Ollama ve Gemini sağlayıcıları açıkça yapılandırıldığında kullanılır.

## İlk gerçek uçtan uca akış

`workspace_audit` görevi izinli çalışma klasörünü inceler. Yönetici görev atar; uzman gerçek dosya envanteri ve SHA-256 kanıtları üretir; kalite kontrolü ve bağımsız denetçi kanıtları kontrol eder. Kayıtlar görev kimliğine bağlıdır. Doğrulanmayan veya değiştirilmiş çıktı reddedilir. Yeniden deneme sınırı vardır.

Bu akış bir LLM konuşma simülasyonu değildir. Dosya araçları gerçekten çalışır; buna karşılık dosya denetimi tek başına mobil uygulama üretiminin, sosyal medya paylaşımının veya WhatsApp görüşmesinin tamamlandığı anlamına gelmez.

Görevler `PENDING → PLANNING → IN_PROGRESS → REVIEW` yolundan sonra `APPROVED`, `REVISION_REQUIRED`, `FAILED` veya `BLOCKED` durumuna gelir. Operatör eylemleri `PAUSED` ve `CANCELLED` durumlarını da kullanır. İşçi düzenli kontrol noktalarında iptal, duraklatma, zaman aşımı ve genel durdurma anahtarını denetler. Geri alınamaz dış işlemler çekirdekte otomatik uygulanmaz.

## Sınırlar ve kanıt

Dosya kökü dışına çıkış, sembolik bağlantıyla kaçış ve gizli oturum / anahtar dosyaları araç politikasıyla sınırlandırılır. API token ister; ilk kurulumda token veri klasörüne üretilir. Panel, SDK ve olay akışı aynı kimlik doğrulamayı kullanır. Veritabanı olayları ile araç çağrıları, atama, hata, yeniden deneme ve son kararı izlenebilir kılar.

LLM yanıtı onay, yetki veya araç başarısı sayılmaz. Haricî içerik veri olarak ele alınır; komut yetkisi taşımaz. Genel amaçlı kabuk yürütme ve dağıtım araçları ilk teslimata dahil değildir. Ayrı işletim sistemi sandbox'ı kurulmadan keyfi kod çalıştırılmamalıdır.

## Dizin yapısı

```text
backend/company/        API, yapılandırma, kalıcı depolama, motor, araçlar, 35 rol
frontend/               React / TypeScript paneli ve Vite üretim derlemesi
kado_bridge/            bağımsız SDK, olaylar, görev, WhatsApp ve ses sözleşmeleri
scripts/                Windows yaşam döngüsü ve salt okunur KADO inceleyicisi
tests/                  çalıştırılabilir çekirdek ve sözleşme testleri
data/                   yerel token, veritabanı, kanıtlar; teslimata dahil edilmez
```

Gerçek Windows KADO kaynakları ve mevcut WhatsApp oturumu bu ortamda bulunmamaktadır. Bu bileşenlerin iç API'leri varsayılmamıştır. Üretim entegrasyonunun son adımı, mevcut kodun salt okunur incelenmesi ve açık adaptör eşlemesidir.
