KADO AJAN MOTORU - bagimsiz prototip

Bu ilk surum gercek gorev kuyrugu, yerel Ollama uzerinden taslak kod/icerik uretimi, AST sozdizimi denetimi ve rapor kaydi yapar. 19 uzmani gercekten calistirdigi iddia edilmez. Mevcut KADO veritabanina veya WhatsApp'a baglanmaz. Kodlari calistirmaz; sosyal medya hesaplarinda yayin yapmaz.

Kurulum: Klasoru C:\KADO\KADO-AJANLAR\kado_motor altina kopyalayin.
Ollama yerelde calismali; qwen2.5:3b modeli yuklu olmali.

Yeni bir PowerShell penceresinde:
$py='C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe'
$motor='C:\KADO\KADO-AJANLAR\kado_motor\kado_motor.py'
& $py $motor ekle kod 'Cocuklar icin basit sayi tahmin oyunu yaz'
& $py $motor ekle paylasim 'Han Toys oyuncak tanitimi'
& $py $motor durum

BASLAT.ps1 dosyasini PowerShell ile calistirin. Surekli islemek icin pencere acik kalmali. Baslatma komutu:
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\KADO\KADO-AJANLAR\kado_motor\BASLAT.ps1'

Ciktilar kado_motor\ciktilar klasorundedir. Uretilen kod calistirilmaz. Otomatik yayinlama yoktur.
