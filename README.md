# KADO OMEGA

Mevcut KADO kaynaklarının korunarak bütünleştirilmesi. Bu depoda sesli asistan, eski ajan motorları, Emine/Influencer Studio ve ayrı AI Company çekirdeği birlikte bulunur. Bunların bulunması bütün sistemin uçtan uca çalıştığını göstermez.

İlk kaynak sürümü ve mevcut durum: [kurtarma envanteri](docs/OMEGA_KURTARMA.md).

## Windows girişleri

- `KADO_KUR.bat`: mevcut AI Company kurulumunu ve panel derlemesini çalıştırır.
- `KADO_BASLAT.bat`: görev motoru ve paneli başlatır; bu giriş eski sesli KADO'yu otomatik başlatmaz.
- `KADO_DURDUR.bat`: yalnızca bu çekirdeğin sahip olduğu backend sürecini durdurur.
- `KADO_TEST.bat`: çekirdek testleri ve panel derlemesi.
- `KADO_YEDEKLE.bat`: kapalı AI Company veri klasörünü bütünlük manifestiyle yedekler.
- `KADO_GERI_YUKLE.bat "YEDEK.zip" "YENI_KLASOR"`: doğrulanmış yedeği yeni klasöre açar.

Python 3.12 ve Node.js 22+ gerekir. Ayrıntılı kurulum: [AI Company](KADO-AI-COMPANY/KADO-AI-COMPANY/README.md). Eski sesli asistanı bağlama prosedürü ve sürüm hash kontrolü ayrı [entegrasyon rehberindedir](KADO-AI-COMPANY/KADO-AI-COMPANY/KADO_ENTEGRASYON_REHBERI.md).

Yeni yedekleme eski KADO/WhatsApp hafızasının veya tüm bilgisayarın yedeği değildir. [Kurtarma kapsamını](KADO-AI-COMPANY/KADO-AI-COMPANY/RECOVERY.md) okuyun. Gerçek Windows süreçleri, mikrofon, WhatsApp hesabı, sosyal yayın ve Emine video üretimi bu değişiklikte doğrulanmadı.
