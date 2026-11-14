"""KADO onay merkezi: bekleyen ('review') isleri listele, goster, onayla, reddet.
Onay = sadece KAYIT. Hicbir sey yayinlanmaz, hicbir kod calistirilmaz.
Onaylanan is .done, reddedilen .failed olur (V4 gorev merkezi bunu gorur). Karar onaylar\\ klasorune yazilir.
Kullanim:
  python kado_onay.py listele
  python kado_onay.py goster ID|son
  python kado_onay.py onayla ID [not]
  python kado_onay.py reddet ID sebep
  ID yerine ayirt edici bir parca yazmak yeter (ornek: faf441).
"""
import datetime, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent
BASE = ROOT / "kado_agent_motor"
QUEUE, OUT, ONAY = BASE / "kuyruk", BASE / "ciktilar", BASE / "onaylar"


def _is(p):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def bekleyenler(queue=QUEUE):
    return [(p.stem, str(_is(p).get("kind", "?")), str(_is(p).get("goal", ""))[:70]) for p in sorted(queue.glob("*.review"))]


def coz(parca, queue=QUEUE):
    if parca == "son":
        r = sorted(queue.glob("*.review"), key=lambda p: p.stat().st_mtime)
        if not r:
            raise SystemExit("BULUNAMADI: bekleyen is yok")
        return r[-1].stem
    m = [p.stem for p in sorted(queue.glob("*.review")) if parca in p.stem]
    if parca in m:
        return parca
    if len(m) == 1:
        return m[0]
    if not m:
        raise SystemExit(f"BULUNAMADI: '{parca}' 'review' durumunda degil")
    raise SystemExit("BIRDEN FAZLA ESLESME, daha uzun yaz: " + ", ".join(m))


def goster(jid, out=OUT, satir=70):
    d = out / jid
    for ad in ("icerik_paketi.md", "paylasim_taslagi.txt", "OZET.txt", "SONUC.json"):
        f = d / ad
        if f.exists():
            print(f"=== {f}")
            for s in f.read_text(encoding="utf-8-sig", errors="replace").splitlines()[:satir]:
                print(s)
            return
    print("Bu is icin gosterilecek dosya bulunamadi:", d)


def karar_ver(jid, karar, not_, queue=QUEUE, onay=ONAY):
    src = queue / (jid + ".review")
    if not src.exists():
        raise SystemExit(f"BULUNAMADI: {jid} 'review' durumunda degil")
    hedef = queue / (jid + (".done" if karar == "ONAYLANDI" else ".failed"))
    if hedef.exists():
        raise SystemExit("HATA: hedef dosya zaten var, dokunulmadi")
    onay.mkdir(parents=True, exist_ok=True)
    kayit = {"id": jid, "karar": karar, "not": not_, "zaman": datetime.datetime.now().isoformat(timespec="seconds")}
    kf = onay / (jid + ".json")
    kf.write_text(json.dumps(kayit, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        src.rename(hedef)
    except Exception:
        kf.unlink(missing_ok=True)
        raise
    return kayit


def selftest():
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        t = pathlib.Path(t); q = t / "q"; o = t / "o"; a = t / "a"; q.mkdir(); o.mkdir()
        for jid, kind in (("20261111_100000_aaa111", "icerik"), ("20261111_110000_bbb222", "kod")):
            (q / f"{jid}.review").write_text(json.dumps({"id": jid, "kind": kind, "goal": "x"}), encoding="utf-8")
            (o / jid).mkdir(); (o / jid / "icerik_paketi.md").write_text("# test\nTürkçe ğüşiçö", encoding="utf-8-sig")
        assert len(bekleyenler(q)) == 2
        assert coz("aaa111", q) == "20261111_100000_aaa111"
        assert coz("son", q) == "20261111_110000_bbb222" or coz("son", q) == "20261111_100000_aaa111"
        try:
            coz("2026", q); raise AssertionError("coklu eslesme reddedilmeliydi")
        except SystemExit:
            pass
        k = karar_ver("20261111_100000_aaa111", "ONAYLANDI", "iyi", q, a)
        assert (q / "20261111_100000_aaa111.done").exists() and not (q / "20261111_100000_aaa111.review").exists()
        assert json.loads((a / "20261111_100000_aaa111.json").read_text(encoding="utf-8"))["karar"] == "ONAYLANDI"
        karar_ver("20261111_110000_bbb222", "REDDEDILDI", "zayif", q, a)
        assert (q / "20261111_110000_bbb222.failed").exists()
        try:
            karar_ver("20261111_100000_aaa111", "ONAYLANDI", "", q, a); raise AssertionError("ikinci karar reddedilmeliydi")
        except SystemExit:
            pass
        assert not bekleyenler(q)
    print("SELFTEST 5/5 BASARILI: listele, parca esleme, onay, red, cift karar engeli")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = sys.argv[1:]
    if not a:
        print(__doc__); return 1
    c = a[0]
    if c == "selftest":
        return selftest()
    if c == "listele":
        r = bekleyenler()
        print(f"ONAY BEKLEYEN: {len(r)}")
        for jid, kind, goal in r:
            print(f"- {jid} | {kind} | {goal}")
        return 0
    if len(a) < 2:
        print("ID gerekli. Ornek: python kado_onay.py", c, "faf441"); return 1
    jid = coz(a[1])
    if c == "goster":
        goster(jid); return 0
    if c in ("onayla", "reddet"):
        not_ = " ".join(a[2:])
        if c == "reddet" and not not_:
            print("Red icin kisa bir sebep yaz."); return 1
        k = karar_ver(jid, "ONAYLANDI" if c == "onayla" else "REDDEDILDI", not_)
        print(f"{k['karar']}: {jid}. Sadece kayit yapildi; hicbir sey yayinlanmadi veya calistirilmadi.")
        return 0
    print("Bilinmeyen komut:", c); return 1


if __name__ == "__main__":
    sys.exit(main())
