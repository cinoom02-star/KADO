# -*- coding: utf-8 -*-
"""KADO ses -> icerik hatti koprusu.
Kullanim:
  python kado_ses_icerik_koprusu.py baslat "PROJE ADI" [--yeniden]
  python kado_ses_icerik_koprusu.py durum
Sadece projeler.json'daki projeleri calistirir. Yayin yapmaz, onay vermez.
Sonuc: KADO'nun sesli okuyacagi kisa Turkce cumle (stdout).
"""
import sys, re, json, subprocess, time, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJELER = ROOT / "projeler.json"
NOBETCI = ROOT / "kado_nobetci.py"
ONAY = ROOT / "kado_onay.py"
LOCK = ROOT / "memory" / "nobetci.lock"
PY = ROOT / ".venv" / "Scripts" / "python.exe"

_TR = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosuCGIOSUaiu")


def _n(s):
    return str(s).translate(_TR).lower().strip()


def _projeler():
    try:
        return json.loads(PROJELER.read_text(encoding="utf-8-sig"))
    except Exception:
        return []


def _kilit_aktif():
    try:
        return LOCK.exists() and (time.time() - LOCK.stat().st_mtime) < 6 * 3600
    except Exception:
        return False


def baslat(ad, yeniden):
    if not NOBETCI.is_file():
        return "Nobetci dosyasi bulunamadi. Baslatilmadi."
    liste = _projeler()
    adlar = [p.get("ad", "") for p in liste if p.get("ad")]
    if not adlar:
        return "Proje listesi bos. Baslatilmadi."
    hedef = None
    q = _n(ad)
    for a in adlar:
        if _n(a) == q:
            hedef = a
            break
    if hedef is None and q:
        eslesen = [a for a in adlar if q in _n(a) or _n(a) in q]
        if len(eslesen) == 1:
            hedef = eslesen[0]
    if hedef is None:
        return "Bu isimde proje bulamadim. Kayitli projeler: " + ", ".join(adlar) + ". Baslatilmadi."
    if _kilit_aktif():
        return "Icerik hatti su an zaten calisiyor. Yeni is baslatilmadi."
    py = str(PY) if PY.is_file() else sys.executable
    cmd = [py, str(NOBETCI), "--proje", hedef]
    if yeniden:
        cmd.append("--zorla")
    logdir = ROOT / "logs"
    logdir.mkdir(exist_ok=True)
    logp = logdir / ("sesli_icerik_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".log")
    with open(logp, "ab") as lf:
        subprocess.Popen(cmd, cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=lf,
                         stderr=subprocess.STDOUT,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return (hedef + " icin icerik, denetim, kart ve video hatti baslatildi. Birkac dakika surer, "
            "bilgisayar yavaslayabilir. Hicbir sey yayinlanmayacak, sonunda senin onayini bekleyecek.")


def durum():
    parca = []
    parca.append("Icerik hatti su an calisiyor." if _kilit_aktif() else "Icerik hatti su an calismiyor.")
    try:
        loglar = sorted((ROOT / "raporlar").glob("nobetci_*.log"))
        if loglar:
            son = [l for l in loglar[-1].read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()][-3:]
            if son:
                parca.append("Son kayit: " + " ".join(x.split("] ", 1)[-1] for x in son))
    except Exception:
        pass
    try:
        r = subprocess.run([str(PY) if PY.is_file() else sys.executable, str(ONAY), "listele"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=20, cwd=str(ROOT))
        satirlar = [l for l in r.stdout.splitlines() if l.startswith("- ")]
        if satirlar:
            parca.append("Onay bekleyen " + str(len(satirlar)) + " paket var: " +
                         "; ".join(s[2:].split(" | ")[0][-6:] + " " + (s.split(" | ")[2][:40] if s.count(" | ") >= 2 else "")
                                   for s in satirlar[:3]))
        else:
            parca.append("Onay bekleyen paket yok.")
    except Exception:
        parca.append("Onay listesi okunamadi.")
    parca.append("Hicbir sey yayinlanmadi.")
    return " ".join(parca)


def yayin():
    yp = ROOT / "kado_yayin_paketi.py"
    if not yp.is_file():
        return "Yayin paketi dosyasi bulunamadi."
    try:
        r = subprocess.run([str(PY) if PY.is_file() else sys.executable, str(yp), "--hepsi"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=100, cwd=str(ROOT))
    except Exception as e:
        return "Yayin paketi hazirlanamadi: " + str(e)[:80]
    out = r.stdout or ""
    hazir = re.findall(r"(?m)^HAZIR: (\S+)", out)
    if hazir:
        return (str(len(hazir)) + " onayli paket yayin klasorune hazirlandi: " +
                ", ".join(h[-6:] for h in hazir) +
                ". Hicbir sey yayinlanmadi, paylasim sende.")
    if "yeni onayli paket yok" in out:
        return "Hazirlanacak yeni onayli paket yok."
    return "Yayin paketi hazirlanamadi."


if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        if a and a[0] == "baslat":
            yen = "--yeniden" in a
            ad = " ".join(x for x in a[1:] if x != "--yeniden")
            print(baslat(ad, yen))
        elif a and a[0] == "durum":
            print(durum())
        elif a and a[0] == "yayin":
            print(yayin())
        else:
            print("Kullanim: baslat \"PROJE\" [--yeniden] | durum | yayin")
    except Exception as e:
        print("Hata: " + str(e)[:150])
