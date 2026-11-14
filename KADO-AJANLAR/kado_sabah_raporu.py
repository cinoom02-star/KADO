"""KADO sabah raporu: son N saatte neler oldu, neler onay bekliyor, neler hata verdi.
Salt okunur (sadece raporlar\\sabah_*.md dosyasi yazar). Kullanim:
  python kado_sabah_raporu.py [--saat 24]
  python kado_sabah_raporu.py selftest
"""
import argparse, datetime, json, pathlib, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
BASE = ROOT / "kado_agent_motor"
QUEUE, ONAY = BASE / "kuyruk", BASE / "onaylar"
RAPOR = ROOT / "raporlar"
LOCK = ROOT / "kado_v4_motor.lock"
OLLAMA = "http://127.0.0.1:11434/api/tags"


def _is(p):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def ollama_acik(url=OLLAMA):
    try:
        urllib.request.urlopen(url, timeout=2).read(); return True
    except Exception:
        return False


def uret(queue=QUEUE, onay=ONAY, lock=LOCK, saat=24, simdi=None, ollama=None):
    simdi = simdi or time.time()
    esik = simdi - saat * 3600
    ollama = ollama_acik() if ollama is None else ollama
    sayac = {}
    pencere = {"done": [], "failed": [], "review": []}
    bekleyen_json = []
    for p in sorted(queue.glob("*")):
        s = p.suffix[1:]
        sayac[s] = sayac.get(s, 0) + 1
        j = _is(p)
        satir = f"{p.stem} | {j.get('kind', '?')} | {str(j.get('goal', ''))[:60]}"
        if s == "json":
            bekleyen_json.append(satir)
        elif s in pencere and p.stat().st_mtime >= esik:
            pencere[s].append(satir)
    kararlar = []
    for p in sorted(onay.glob("*.json")) if onay.exists() else []:
        if p.stat().st_mtime >= esik:
            k = _is(p)
            kararlar.append(f"{k.get('id')} | {k.get('karar')} | {k.get('not', '')}")
    tum_review = [f"{p.stem} | {_is(p).get('kind', '?')} | {str(_is(p).get('goal', ''))[:60]}" for p in sorted(queue.glob("*.review"))]
    t = datetime.datetime.fromtimestamp(simdi).strftime("%d.%m.%Y %H:%M")
    r = [f"# KADO Sabah Raporu - {t}", f"Pencere: son {saat} saat", "",
         "## Ozet",
         f"- Onay bekleyen: {len(tum_review)}",
         f"- Son {saat} saatte tamamlanan: {len(pencere['done'])}, hata/red: {len(pencere['failed'])}",
         f"- Motor kuyrugunda bekleyen (.json): {len(bekleyen_json)}",
         f"- Ollama (yerel model): {'ACIK' if ollama else 'KAPALI - icerik uretilemez'}",
         f"- V4 motor kilidi: {'VAR (calisiyor olabilir)' if lock.exists() else 'YOK (kuyruktaki .json gorevler islenmez)'}", ""]
    r += ["## Onay bekleyenler (komut: python kado_onay.py onayla|reddet ID)"] + ([f"- {x}" for x in tum_review] or ["- yok"]) + [""]
    r += [f"## Son {saat} saatte tamamlananlar"] + ([f"- {x}" for x in pencere["done"]] or ["- yok"]) + [""]
    r += [f"## Son {saat} saatte hata/red"] + ([f"- {x}" for x in pencere["failed"]] or ["- yok"]) + [""]
    r += [f"## Son {saat} saatte verdigin kararlar"] + ([f"- {x}" for x in kararlar] or ["- yok"]) + [""]
    if bekleyen_json:
        r += ["## Motorda bekleyen gorevler"] + [f"- {x}" for x in bekleyen_json] + [""]
    r += ["## Uyarilar"]
    uy = []
    if not ollama:
        uy.append("Ollama kapali: ollama serve ile ac.")
    if bekleyen_json and not lock.exists():
        uy.append("Motor kapali gorunuyor, bekleyen .json gorevler islenmeyecek.")
    if len(tum_review) > 10:
        uy.append("10'dan fazla is onay bekliyor, kuyrugu temizle.")
    r += ([f"- {x}" for x in uy] or ["- yok"])
    r += ["", "Bu rapor sadece bilgi verir; hicbir sey yayinlanmadi."]
    return "\n".join(r)


def selftest():
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        t = pathlib.Path(t); q = t / "q"; a = t / "a"; q.mkdir(); a.mkdir()
        (q / "1.review").write_text(json.dumps({"kind": "icerik", "goal": "Türkçe ğüş"}), encoding="utf-8")
        (q / "2.done").write_text(json.dumps({"kind": "kod", "goal": "x"}), encoding="utf-8")
        (q / "3.failed").write_text(json.dumps({"kind": "icerik", "goal": "y"}), encoding="utf-8")
        (q / "4.json").write_text(json.dumps({"kind": "arastirma", "goal": "z"}), encoding="utf-8")
        (a / "2.json").write_text(json.dumps({"id": "2", "karar": "ONAYLANDI", "not": "iyi"}), encoding="utf-8")
        eski = q / "0.done"; eski.write_text("{}", encoding="utf-8")
        import os; os.utime(eski, (1, 1))
        r = uret(q, a, t / "yok.lock", 24, ollama=False)
        assert "Onay bekleyen: 1" in r and "tamamlanan: 1, hata/red: 1" in r
        assert "0 |" not in r.split("tamamlananlar")[1].split("##")[0]
        assert "KAPALI" in r and "YOK" in r and "ONAYLANDI" in r and "Motor kapali" in r
    print("SELFTEST 4/4 BASARILI: sayim, zaman penceresi, kararlar, uyarilar")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        return selftest()
    ap = argparse.ArgumentParser(); ap.add_argument("--saat", type=int, default=24)
    a = ap.parse_args()
    r = uret(saat=a.saat)
    print(r)
    RAPOR.mkdir(exist_ok=True)
    f = RAPOR / ("sabah_" + datetime.datetime.now().strftime("%Y%m%d_%H%M") + ".md")
    f.write_text(r, encoding="utf-8-sig")
    print("\nKAYDEDILDI:", f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
