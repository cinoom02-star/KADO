# KADO Kullanım Kılavuzu (v1)

Kural: KADO hiçbir şeyi kendi başına yayınlamaz, mesaj atmaz, para harcamaz. Her paket senin onayını bekler.

## Sesle (KADO'yu aç, konuş)
| Söyle | Olur |
|---|---|
| "Han Toys için içerik hazırla" | İçerik → denetçi → kart → video üretir (birkaç dakika, PC yavaşlar). Bitince KADO "paket hazır" der. |
| "İçerik hattı ne durumda?" | Çalışıyor mu, onay bekleyen paket var mı söyler. |
| "Onaylı paketi yayına hazırla" | ONAYLI paketleri `yayin_paketleri` klasörüne ve zip'e koyar. Yayınlamaz. |

## Elle (PowerShell, `$py = "C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe"`)
- Onay bekleyenler: `& $py kado_onay.py listele`
- Onayla / reddet: `& $py kado_onay.py onayla 6HANE` / `... reddet 6HANE "sebep"` (sebep sonraki üretimde hafızaya girer)
- Denetle (düzeltir): `& $py kado_denetci.py 6HANE`  Sadece bak: `--sadece-kontrol`  Tanıtım paketi için `--hedef "açıklama"` şart.
- Tanıtım paketi: `& $py kado_tanitim_paketi.py "KADO" "açıklama" --asama cikis-oncesi`
- Uzman durumu: `& $py kado_uzman_durum.py`
- Tercih ekle: `& $py kado_hafiza.py not "Han Toys" "abartılı vaat verme"`

## Paylaşırken
`yayin_paketleri\<ID>.zip` → telefona aktar → aç → metni oku, görselleri ve videoyu paylaş. Videoyu sessiz üretir; müziği Instagram'dan sen seç. Paylaşmadan önce `YAYIN_NOTU.txt` kontrol listesine bak.

## Bozulursa geri alma
- Sesli komut yaması: `kado_ses_yama.py --geri` ve `kado_yayin_yama.py --geri`
- Bildirim yaması: `kado_bildirim_yama.py --geri`
- Hepsi sonrası KADO'yu kapatıp yeniden aç. Yedekler: `C:\KADO\KADO-AJANLAR\yedekler`
- Üretim takıldıysa ve "zaten çalışıyor" diyorsa: `memory\nobetci.lock` dosyasını sil (6 saatten eskiyse kendiliğinden geçersiz olur).

## Henüz yok (v2)
Instagram'a otomatik yayın, takipçi/beğeni takibi, gerçek internet araştırması, KADO'nun kendi kendine yeni ajan önermesi.
Not: Ana KADO uygulaması başka bir projeden türetildi. Satmayı düşünüyorsan LICENSE.md dosyasını oku.
