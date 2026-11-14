# KADO AI Company — yerel çekirdek teslimatı

Mevcut **KADO CEO olarak kalır**. Bu paket KADO'ya bağlanacak bağımsız görev motorunu, 35 rol tanımını, gerçek dosya araçlarını, kanıt denetimini, paneli ve entegrasyon SDK'sını sağlar. Tam kaynak kodu yereldir; Lovable, Base44 veya barındırılan bir geliştirme platformuna çalışma zamanı bağımlılığı yoktur.

Bu ilk teslimattır. Gerçek KADO kurulumu ve WhatsApp hesabı burada bulunmadığı için gerçek mesaj, ses ve arama bağlantısı **doğrulanmamıştır**. Genel ürün geliştirme, sosyal yayınlama ve video üretiminin tümü tamamlanmış değildir. Ayrıntılar: [PHASE_STATUS.md](PHASE_STATUS.md), [WHATSAPP_KOPRU_ANALIZI.md](WHATSAPP_KOPRU_ANALIZI.md).

## Windows'ta başlatma

Gerekenler: Windows 10/11, Python 3.12 ve Node.js 22 veya üzeri; ilk kurulum için paket depolarına internet erişimi. Yönetici yetkisi gerekmez. Mevcut KADO süreçlerini kapatmayın.

1. Paketi örneğin `C:\KADO\KADO-AI-COMPANY` klasörüne çıkarın. `C:\KADO\kado` veya `C:\KADO\KADO-AJANLAR` içine kurmayın.
2. `KURULUM.bat` çalıştırın. Ayrı `.venv` ortamı ve panel derlemesi hazırlanır.
3. İsteğe bağlı `.env.example` dosyasını `.env` adıyla kopyalayın ve sağlayıcıları yapılandırın. Anahtarları kaynak koda yazmayın.
4. `BASLAT.bat` çalıştırın; panel `http://127.0.0.1:8765` adresindedir.
5. Panelin istediği token'ı kendi bilgisayarınızdaki `data\api-token.txt` dosyasından alın. Token'ı paylaşmayın.
6. Doğrulama için `TEST_ET.bat`; yalnızca bu paketi durdurmak için `DURDUR.bat` kullanın.

`KADO_KURULUM.bat`, `KADO_BASLAT.bat` ve `KADO_DURDUR.bat` eşdeğer kısayollardır. Kurulum dosyaları mevcut KADO kaynaklarını, WhatsApp oturumunu veya ses ayarlarını düzenlemez.

## İlk gerçek görevi çalıştırma

`data\workspace` içine kendi oluşturduğunuz, gizli bilgi içermeyen birkaç metin dosyası koyun. Panelde çalışma alanı denetimi (`workspace_audit`) oluşturun; yol `.` olsun. Görev ayrıntısında yönetici atamasını, uzman araç çağrılarını, gerçek dosya SHA-256 kanıtlarını ve denetçi kararını izleyin. Görev boş bir çalışma alanında da dürüstçe boş envanter raporu üretir.

`llm_task` gerçek sağlayıcı gerektirir. Ollama veya Gemini yapılandırılmadıysa görev `BLOCKED` olur. Ajan sayısı, eşzamanlı çalışan ağır model sayısı değildir. Donanımınız ölçülmeden eşzamanlılığı yükseltmeyin.

## Linux / macOS geliştirme

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
python -m uvicorn company.api:app --app-dir backend --host 127.0.0.1 --port 8765
```

Ayrı geliştirme paneli için `npm --prefix frontend run dev` kullanılır; Vite `/api` isteklerini yerel backend'e iletir. Üretim paneli aynı backend portundan sunulur. Testler `python -m pytest -q` ile çalışır. KADO köprü kontrolü için [KADO_ENTEGRASYON_REHBERI.md](KADO_ENTEGRASYON_REHBERI.md) belgesini izleyin.

## Veriler ve işletim

Varsayılan SQLite dosyası, token ve çalışma çıktıları `data/` altındadır; kaynak paketinde gerçek kullanıcı verisi bulunmamalıdır. Yedekleme öncesi `DURDUR.bat` ile bu servisi kapatıp `data/` klasörünü güvenli bir konuma kopyalayın. Geri yükleme de servis kapalıyken yapılır. Çalışan SQLite dosyasını tek başına kopyalamak tutarlı yedek garantisi vermez.

İsteğe bağlı Docker Compose kurulumu için [ARCHITECTURE.md](ARCHITECTURE.md) ve `.env.example` dosyasını inceleyin. PostgreSQL desteği yapılandırılabilir; bu teslimatta PostgreSQL veya Docker gerçekten çalıştırılmadıysa test raporunda doğrulanmış yazılmaz.

Docker ile SQLite kurulumu `docker compose up --build -d company` komutuyla başlar. Token container'ın `/app/data/api-token.txt` dosyasındadır; dosyayı `docker compose cp company:/app/data/api-token.txt data/docker-api-token.txt` ile kendi makinenize alın. Önce yerel `data` klasörünü oluşturun. Compose verileri adlandırılmış volume'da tutar; `docker compose down -v` verileri siler, rutin durdurma için kullanmayın. Windows'ta yerel Ollama'ya container'dan erişim için `.env` içindeki `OLLAMA_BASE_URL=http://host.docker.internal:11434` olmalıdır.

PostgreSQL seçeneğinde `.env` içinde güçlü `POSTGRES_PASSWORD` belirleyin. Yalnızca veritabanını başlatmak için `docker compose --profile postgres up -d db` kullanılır. Native backend için `DATABASE_URL=postgresql+psycopg://kado_company:URL_KODLU_PAROLA@127.0.0.1:5432/kado_company`; Compose `company` servisi için aynı URL'de sunucu `db` olur. Ayar sonrası uygulamayı yeniden başlatın. Veritabanı servisini açmak mevcut SQLite verisini otomatik taşımaz.

Başvuru belgeleri: [mimari](ARCHITECTURE.md), [35 ajan](KADO_35_AJAN_MIMARISI.md), [güvenlik](SECURITY.md), [KADO bağlantısı](INTEGRATION_KADO.md), [WhatsApp arama prosedürü](WHATSAPP_ARAMA_TESTLERI.md), [test raporu](TEST_SONUCLARI.md).
