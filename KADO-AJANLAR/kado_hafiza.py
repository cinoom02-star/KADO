# -*- coding: utf-8 -*-
"""KADO HAFIZA - onay/red kararlarindan ve senin notlarindan proje basina kalici hafiza tutar.
Sadece memory\\kado_hafiza.json dosyasina yazar. Hicbir seyi yayinlamaz/calistirmaz.
Kullanim:
  python kado_hafiza.py guncelle              # onaylar\\*.json kararlarini hafizaya isler
  python kado_hafiza.py not "Han Toys" "abartili vaat kullanma"   # kalici tercih ekle
  python kado_hafiza.py sil "Han Toys" 1      # tercih sil (sira numarasi)
  python kado_hafiza.py ozet                  # hafizayi goster
  python kado_hafiza.py baglam "Han Toys"     # icerik hattina verilecek metni goster
  python kado_hafiza.py selftest
"""
import sys, json, datetime, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GURULTU = ("deneme", "eski", "test")   # bu kelimeleri iceren red notlari baglama girmez
MAX_BAGLAM = 380


def _yollar(root):
    root = Path(root)
    return (root / "memory" / "kado_hafiza.json",
            root / "kado_agent_motor" / "onaylar",
            root / "kado_agent_motor" / "kuyruk")


def yukle(root=ROOT):
    f, _, _ = _yollar(root)
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {"projeler": {}}


def kaydet(h, root=ROOT):
    f, _, _ = _yollar(root)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(h, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(f)


def _proje(h, ad):
    return h["projeler"].setdefault(ad, {"tercihler": [], "kararlar": []})


def _jgoal(queue, jid):
    for p in queue.glob(jid + ".*"):
        try:
            return str(json.loads(p.read_text(encoding="utf-8-sig")).get("goal", ""))
        except Exception:
            pass
    return ""


def guncelle(root=ROOT):
    """onaylar\\*.json kararlarini proje adina gore hafizaya isler. Yeni islenen sayisini dondurur."""
    _, onay, queue = _yollar(root)
    h = yukle(root)
    yeni = 0
    if not onay.exists():
        return 0
    for p in sorted(onay.glob("*.json")):
        try:
            k = json.loads(p.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        jid = k.get("id")
        goal = _jgoal(queue, jid)
        if ":" not in goal:
            continue   # kod gorevleri vb. proje adi tasimaz
        ad = goal.split(":", 1)[0].strip()
        if not ad:
            continue
        pr = _proje(h, ad)
        if any(x.get("id") == jid for x in pr["kararlar"]):
            continue
        pr["kararlar"].append({"id": jid, "karar": k.get("karar"), "not": k.get("not", ""), "zaman": k.get("zaman", "")})
        yeni += 1
    if yeni:
        kaydet(h, root)
    return yeni


def not_ekle(ad, metin, root=ROOT):
    h = yukle(root)
    pr = _proje(h, ad)
    if metin not in pr["tercihler"]:
        pr["tercihler"].append(metin)
    kaydet(h, root)


def sil(ad, sira, root=ROOT):
    h = yukle(root)
    pr = h["projeler"].get(ad)
    if not pr or not (1 <= sira <= len(pr["tercihler"])):
        raise SystemExit("BULUNAMADI: proje ya da sira numarasi yok")
    pr["tercihler"].pop(sira - 1)
    kaydet(h, root)


def baglam(ad, root=ROOT):
    """Icerik hattina eklenecek kisa metin. Hafiza bossa '' doner."""
    h = yukle(root)
    pr = h["projeler"].get(ad)
    if not pr:
        return ""
    parcalar = []
    if pr["tercihler"]:
        parcalar.append("Patronun tercihleri: " + "; ".join(pr["tercihler"][-5:]))
    sebepler = []
    for x in pr["kararlar"][-10:]:
        n = (x.get("not") or "").strip()
        if x.get("karar") == "REDDEDILDI" and n and not any(g in n.lower() for g in GURULTU):
            sebepler.append(n)
    if sebepler:
        parcalar.append("Daha once reddedilme sebepleri (tekrarlama): " + "; ".join(sebepler[-3:]))
    onayli = sum(1 for x in pr["kararlar"] if x.get("karar") == "ONAYLANDI")
    if onayli:
        parcalar.append(f"{onayli} paket onaylandi, ayni ton ve duzeni koru")
    s = ". ".join(parcalar)
    return s[:MAX_BAGLAM]


def ozet(root=ROOT):
    h = yukle(root)
    if not h["projeler"]:
        print("Hafiza bos. Ornek: python kado_hafiza.py not \"Han Toys\" \"abartili vaat kullanma\"")
        return
    for ad, pr in h["projeler"].items():
        on = sum(1 for x in pr["kararlar"] if x.get("karar") == "ONAYLANDI")
        rd = sum(1 for x in pr["kararlar"] if x.get("karar") == "REDDEDILDI")
        print(f"## {ad}  (onay: {on}, red: {rd})")
        for i, t in enumerate(pr["tercihler"], 1):
            print(f"  tercih {i}: {t}")
        for x in pr["kararlar"][-5:]:
            print(f"  - {x.get('zaman','')[:16]} {x.get('karar')} {x.get('id')} {x.get('not','')}")


def selftest():
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        _, onay, q = _yollar(t)
        onay.mkdir(parents=True); q.mkdir(parents=True)
        def mk(jid, suf, goal, karar, not_):
            (q / f"{jid}.{suf}").write_text(json.dumps({"kind": "icerik", "goal": goal}), encoding="utf-8")
            (onay / f"{jid}.json").write_text(json.dumps({"id": jid, "karar": karar, "not": not_, "zaman": "2026-11-11T12:00:00"}), encoding="utf-8")
        mk("a1", "done", "Han Toys: oyuncak", "ONAYLANDI", "")
        mk("a2", "failed", "Han Toys: oyuncak", "REDDEDILDI", "garantili vaat var")
        mk("a3", "failed", "Han Toys: oyuncak", "REDDEDILDI", "deneme gorevi")
        mk("a4", "failed", "Python ile toplama yaz", "REDDEDILDI", "x")      # proje adi yok
        assert guncelle(t) == 3 and guncelle(t) == 0
        not_ekle("Han Toys", "sade ve samimi dil", t)
        b = baglam("Han Toys", t)
        assert "sade ve samimi" in b and "garantili vaat" in b and "deneme" not in b and "1 paket onaylandi" in b
        assert len(b) <= MAX_BAGLAM and baglam("Yok", t) == ""
        sil("Han Toys", 1, t)
        assert "sade ve samimi" not in baglam("Han Toys", t)
    print("SELFTEST 5/5 BASARILI: isleme, tekrar engeli, kod gorevi atlama, gurultu suzme, tercih ekle/sil")


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
    if c == "guncelle":
        print(f"HAFIZA GUNCELLENDI: {guncelle()} yeni karar islendi"); return 0
    if c == "ozet":
        ozet(); return 0
    if c == "not" and len(a) >= 3:
        not_ekle(a[1], " ".join(a[2:])); print("TERCIH EKLENDI:", a[1]); return 0
    if c == "sil" and len(a) == 3 and a[2].isdigit():
        sil(a[1], int(a[2])); print("TERCIH SILINDI"); return 0
    if c == "baglam" and len(a) >= 2:
        print(baglam(" ".join(a[1:])) or "(bos)"); return 0
    print("Bilinmeyen komut:", c); return 1


if __name__ == "__main__":
    sys.exit(main())
