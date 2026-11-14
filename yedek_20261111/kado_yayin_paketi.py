# -*- coding: utf-8 -*-
"""KADO elle yayin paketi: ONAYLI paketi tek klasore (ve zip'e) toplar.
Yayin YAPMAZ, hicbir hesaba baglanmaz. Telefona aktarip elle paylasmak icindir.
Kullanim:
  python kado_yayin_paketi.py ID [ID ...]   (kisa ID kabul: 19c228)
  python kado_yayin_paketi.py --hepsi       (onayli ve henuz hazirlanmamis hepsi)
  python kado_yayin_paketi.py --ac          (islem sonunda klasoru ac)
  python kado_yayin_paketi.py selftest
"""
import sys, os, shutil, json, datetime, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MOTOR = ROOT / "kado_agent_motor"
CIKTI = MOTOR / "ciktilar"
ONAY = MOTOR / "onaylar"
HEDEF = ROOT / "yayin_paketleri"

NOT = """YAYIN NOTU (KADO) - {pid}
Hazirlanma: {ts}
Durum: ONAYLI. KADO bu paketi YAYINLAMADI; paylasim senin elinde.

Icerik:
- {metin}  -> gonderi metni, hashtag ve takvim. Paylasmadan once bir kez oku.
- gorseller\\  -> *_kare.png (gonderi), *_hikaye.png (hikaye)
- video\\reel.mp4  -> sessiz taslak video

Paylasmadan once kontrol:
[ ] Metinde garanti, "en iyi", olmayan ozellik, fiyat ya da indirim iddiasi yok
[ ] Uygulama/urun henuz cikmadiysa "indir" ya da "magazada" gibi ifade yok
[ ] Video sessiz: muzigi paylasim ekranindan kendin sec
[ ] Telefona zip'i aktar (kablo, bulut ya da kendine mesaj), ac, paylas
"""


def _karar(pid):
    """'onay' | 'red' | None. Karar dosyalarinda id ve karar kelimesine bakar."""
    if not ONAY.is_dir():
        return None
    sonuc = None
    for f in sorted(ONAY.glob("*.json")):
        try:
            t = f.read_text(encoding="utf-8", errors="replace").lower()
        except Exception:
            continue
        if pid.lower() not in t and pid.lower() not in f.name.lower():
            continue
        if "reddedildi" in t:
            sonuc = "red"
        elif "onaylandi" in t:
            sonuc = "onay"
    return sonuc


def _coz(kisa):
    if (CIKTI / kisa).is_dir():
        return kisa
    adaylar = [d.name for d in CIKTI.iterdir() if d.is_dir() and d.name.endswith(kisa)] if CIKTI.is_dir() else []
    return adaylar[0] if len(adaylar) == 1 else None


def hazirla(pid):
    kaynak = CIKTI / pid
    k = _karar(pid)
    if k == "red":
        return "ATLANDI: %s reddedilmis, yayin paketi yapilmadi." % pid
    if k != "onay":
        return "ATLANDI: %s icin ONAY kaydi bulunamadi. Once kado_onay.py onayla." % pid
    metin = next((n for n in ("icerik_paketi.md", "tanitim_paketi.md") if (kaynak / n).is_file()), None)
    if metin is None:
        return "ATLANDI: %s icinde metin dosyasi yok." % pid
    hdf = HEDEF / pid
    if hdf.exists():
        shutil.rmtree(hdf)
    hdf.mkdir(parents=True)
    shutil.copy2(kaynak / metin, hdf / metin)
    if (kaynak / "gorseller").is_dir():
        shutil.copytree(kaynak / "gorseller", hdf / "gorseller")
    if (kaynak / "video" / "reel.mp4").is_file():
        (hdf / "video").mkdir()
        shutil.copy2(kaynak / "video" / "reel.mp4", hdf / "video" / "reel.mp4")
    (hdf / "YAYIN_NOTU.txt").write_text(
        NOT.format(pid=pid, ts=datetime.datetime.now().strftime("%d.%m.%Y %H:%M"), metin=metin),
        encoding="utf-8")
    z = shutil.make_archive(str(HEDEF / pid), "zip", str(hdf))
    return "HAZIR: %s\n  KLASOR: %s\n  ZIP: %s\n  DURUM: YAYINLANMADI, paylasim sende" % (pid, hdf, z)


def hepsi():
    if not CIKTI.is_dir():
        return []
    out = []
    for d in sorted(CIKTI.iterdir()):
        if d.is_dir() and _karar(d.name) == "onay" and not (HEDEF / d.name).exists():
            out.append(d.name)
    return out


def selftest():
    global ROOT, MOTOR, CIKTI, ONAY, HEDEF
    tmp = Path(tempfile.mkdtemp())
    ROOT = tmp; MOTOR = tmp / "kado_agent_motor"; CIKTI = MOTOR / "ciktilar"; ONAY = MOTOR / "onaylar"; HEDEF = tmp / "yayin_paketleri"
    ONAY.mkdir(parents=True)
    for pid, karar in (("20261111_000000_aaa111", "ONAYLANDI"), ("20261111_000001_bbb222", "REDDEDILDI"), ("20261111_000002_ccc333", None)):
        d = CIKTI / pid
        (d / "gorseller").mkdir(parents=True); (d / "video").mkdir()
        (d / "icerik_paketi.md").write_text("# test", encoding="utf-8")
        (d / "gorseller" / "kart_1_kare.png").write_bytes(b"x")
        (d / "video" / "reel.mp4").write_bytes(b"x")
        if karar:
            (ONAY / (pid + ".json")).write_text(json.dumps({"id": pid, "karar": karar}), encoding="utf-8")
    ok = 0
    r = hazirla(_coz("aaa111")); ok += r.startswith("HAZIR") and (HEDEF / "20261111_000000_aaa111.zip").is_file() and (HEDEF / "20261111_000000_aaa111" / "video" / "reel.mp4").is_file()
    ok += hazirla("20261111_000001_bbb222").startswith("ATLANDI") and not (HEDEF / "20261111_000001_bbb222").exists()
    ok += hazirla("20261111_000002_ccc333").startswith("ATLANDI")
    ok += _coz("yok999") is None
    ok += hepsi() == []
    shutil.rmtree(tmp, ignore_errors=True)
    print("SELFTEST %d/5 %s" % (ok, "BASARILI" if ok == 5 else "BASARISIZ"))


if __name__ == "__main__":
    a = [x for x in sys.argv[1:]]
    if a and a[0] == "selftest":
        selftest(); sys.exit(0)
    ac = "--ac" in a
    ids = [x for x in a if not x.startswith("--")]
    if "--hepsi" in a:
        ids = hepsi()
        if not ids:
            print("Hazirlanacak yeni onayli paket yok.")
    hedefler = []
    for i in ids:
        c = _coz(i)
        if c is None:
            print("BULUNAMADI:", i)
        else:
            hedefler.append(c)
    for c in hedefler:
        print(hazirla(c))
    if not a:
        print(__doc__)
    if ac and HEDEF.is_dir():
        try:
            os.startfile(str(HEDEF))
        except Exception:
            pass
