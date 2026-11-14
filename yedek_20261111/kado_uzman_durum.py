# -*- coding: utf-8 -*-
"""KADO UZMAN DURUMU - 19 uzmandan hangisinin GERCEKTEN calisan kodu var, durustce listeler.
Sadece OKUR (dosya var mi diye bakar). kado_19_uzman.py'ye dokunmaz. Rapor: raporlar\\uzman_durum.md
Kullanim: python kado_uzman_durum.py
"""
import sys, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# uzman -> (ad, calistiran dosya ya da None, aciklama)
U = [
    ("U01", "Web Arastirmacisi", None, "tanimli; gercek internet aramasi calismiyor (arama sorunu acik)"),
    ("U02", "GitHub Arastirmacisi", None, "tanimli; kismi kod var, bu hatta dogrulanmadi"),
    ("U03", "Rakip Analisti", None, "tanimli; calisan kod dogrulanmadi"),
    ("U04", "Kod Yazari", None, "V4 motorunda kod gorevi var; bu hatta dogrulanmadi"),
    ("U05", "Hata Avcisi", None, "tanimli; kismi (statik) kod, dogrulanmadi"),
    ("U06", "Test Uzmani", None, "tanimli; kismi (statik) kod, dogrulanmadi"),
    ("U07", "Guvenlik Denetcisi", None, "tanimli; kismi (statik) kod, dogrulanmadi"),
    ("U08", "Gorsel Uretici", "kado_gorsel_kart.py", "metin kartlari (kare + hikaye PNG). Yapay zeka gorseli degil"),
    ("U09", "Fotograf Duzenleyici", None, "YOK: kod yazilmadi"),
    ("U10", "Urun Gorseli Uzmani", None, "YOK: kod yazilmadi (gercek urun fotografi gerekir)"),
    ("U11", "Video Uretici", "kado_video.py", "kartlardan sessiz slayt videosu (ffmpeg)"),
    ("U12", "Video Kurgucu", "kado_video.py", "yalnizca slayt birlestirme; altyazi/efekt yok"),
    ("U13", "Video Analizcisi", None, "YOK: kod yazilmadi"),
    ("U14", "Metin Yazari", "kado_icerik_hatti.py", "gonderi metni, yerel model"),
    ("U15", "Sosyal Medya Uzmani", "kado_icerik_hatti.py", "gorsel fikri ve hashtag, yerel model"),
    ("U16", "Yayin Planlayicisi", "kado_yayin_paketi.py", "7 gunluk takvim taslagi + elle yayin paketi. Otomatik yayin YOK"),
    ("U17", "Veri Analisti", None, "tanimli; takipci/begeni takibi yok"),
    ("U18", "Kalite Kontrolcu", "kado_denetci.py", "kod + model denetimi, bolumu yeniden yazdirir"),
    ("U19", "Raporlama Uzmani", "kado_sabah_raporu.py", "sabah raporu (+ kado_envanter.py)"),
]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    out = [f"# KADO UZMAN DURUMU - {datetime.datetime.now():%d.%m.%Y %H:%M}", ""]
    ok = 0
    for uid, ad, dosya, acik in U:
        if dosya and (ROOT / dosya).is_file():
            d, ok = "CALISIYOR", ok + 1
        elif dosya:
            d = "DOSYA EKSIK (" + dosya + ")"
        elif acik.startswith("YOK"):
            d = "YOK"
        else:
            d = "SADECE ISIM"
        out.append(f"- {uid} {ad}: {d} - {acik}")
    out += ["", f"Ozet: {ok} uzman icin calisan kod var, {len(U) - ok} uzman henuz sadece isim ya da yok.",
            "Not: CALISIYOR = dosya mevcut; uretimde kullanildi ya da selftest gecti. Hicbir uzman otomatik yayin yapmaz."]
    rp = ROOT / "raporlar"
    rp.mkdir(exist_ok=True)
    (rp / "uzman_durum.md").write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
