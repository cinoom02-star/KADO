# -*- coding: utf-8 -*-
"""KADO ses -> icerik hatti koprusu (v2). Sesli araclar bu dosyayi cagirir; cikti KADO'nun sesli okuyacagi kisa cumledir.
Komutlar:
  baslat "PROJE" [--yeniden] | durum | yayin
  paketler | oku ID|son|PROJE | onayla ID|son|PROJE [--evet] | reddet ID|son|PROJE "sebep" [--evet] | geri [ID]
  proje-ekle "AD" "hedef" [--platform instagram] [--guncelle] | proje-liste | proje-sil "AD"
  gorev "serbest istek" [--proje AD]
  selftest
Onay = sadece KAYIT: hicbir sey yayinlanmaz. Sesle onay/red iki adimlidir (once soru, sonra --evet, en az 4 sn sonra).
"""
import sys, re, json, subprocess, time, datetime, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJELER = ROOT / "projeler.json"
NOBETCI = ROOT / "kado_nobetci.py"
ONAY = ROOT / "kado_onay.py"
LOCK = ROOT / "memory" / "nobetci.lock"
PY = ROOT / ".venv" / "Scripts" / "python.exe"
BASE = ROOT / "kado_agent_motor"
QUEUE, OUT, ONAYLAR = BASE / "kuyruk", BASE / "ciktilar", BASE / "onaylar"
PEND = ROOT / "memory" / "ses_onay_bekleyen.json"
YAYIN = ROOT / "yayin_paketleri"
TUR = {"icerik": "içerik", "tanitim": "tanıtım", "kod": "kod", "arastirma": "araştırma"}
BEKLE_MIN, BEKLE_MAX = 4, 180
YER_TUTUCU = ("proje adi", "gercek proje adi")
PLATFORMLAR = ("instagram", "tiktok", "youtube", "facebook", "linkedin", "x")

_TR = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosuCGIOSUaiu")


def _n(s):
    return str(s).translate(_TR).lower().strip()


def _j(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _projeler():
    try:
        v = json.loads(PROJELER.read_text(encoding="utf-8-sig"))
        return v if isinstance(v, list) else []
    except Exception:
        return []


def _kilit_aktif():
    try:
        return LOCK.exists() and (time.time() - LOCK.stat().st_mtime) < 6 * 3600
    except Exception:
        return False


# ---------------------------------------------------------------- icerik hatti (v1'den ayni)
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
        s = _j(ROOT / "memory" / "ceo_son.json")
        if s and time.time() - Path(ROOT / "memory" / "ceo_son.json").stat().st_mtime < 24 * 3600:
            parca.append("Genel müdürün son işi: " + str(s.get("ozet", ""))[:160])
        d = _j(ROOT / "memory" / "ceo_defter.json")
        bek = [x for x in (d.get("kayitlar", []) if isinstance(d, dict) else []) if x.get("durum") == "bekliyor"]
        if bek:
            parca.append(str(len(bek)) + " görev uzman olmadığı için deftere yazıldı, yapılmadı.")
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


# ---------------------------------------------------------------- sesle onay / red
def _proje_adi(goal):
    return goal.split(":", 1)[0].strip() if ":" in goal else ""


def bekleyenler(queue=None):
    queue = queue or QUEUE
    r = []
    for p in sorted(Path(queue).glob("*.review")):
        j = _j(p)
        goal = str(j.get("goal", ""))
        r.append({"id": p.stem, "kind": str(j.get("kind", "?")), "goal": goal,
                  "proje": _proje_adi(goal), "mtime": p.stat().st_mtime})
    return r


def _ad(i):
    if i["kind"] == "eylem":  # KADO_EYLEM_V1
        return "Eylem onayı: " + i["goal"].split(":", 1)[-1].strip()[:90]
    return f"{i['proje'] or i['goal'][:30] or 'isimsiz'} {TUR.get(i['kind'], i['kind'])} paketi"


def _saat(i):
    return datetime.datetime.fromtimestamp(i["mtime"]).strftime("%H:%M")


def paket_coz(ifade, items):
    """(item, mesaj). item yoksa mesaj kullaniciya soylenecek soru/uyaridir."""
    if not items:
        return None, "Onay bekleyen paket yok."
    q = _n(ifade)
    en_yeni = max(items, key=lambda i: i["mtime"])
    belirtec = set(q.split())
    if q in ("", "son", "sonuncu", "en son", "son paket", "yeni", "en yeni"):
        return en_yeni, ""
    for t in q.split():
        if len(t) >= 4 and re.fullmatch(r"[0-9a-f]+", t):
            m = [i for i in items if t in i["id"]]
            if len(m) == 1:
                return m[0], ""
    cand = [i for i in items if i["proje"] and _n(i["proje"]) in q]
    if not cand:
        cand = [i for i in items if i["proje"] and len(q) >= 3 and q in _n(i["proje"])]
    for k in TUR:
        if k in q and any(i["kind"] == k for i in cand):
            cand = [i for i in cand if i["kind"] == k]
    if cand and (belirtec & {"yeni", "son"}):
        cand = [max(cand, key=lambda i: i["mtime"])]
    if len(cand) == 1:
        return cand[0], ""
    if len(cand) > 1:
        return None, (f"{cand[0]['proje']} için {len(cand)} paket var: " +
                      ", ".join(f"{TUR.get(i['kind'], i['kind'])} {_saat(i)}" for i in sorted(cand, key=lambda i: i['mtime'])[:5]) +
                      ". Hangisi? 'en yeni içerik' ya da 'tanıtım' diye belirt.")
    return None, ("Bu isimde bekleyen paket bulamadım. Bekleyenler: " +
                  ", ".join(_ad(i) for i in items[:4]) + ".")


def denetci_durumu(jid, out=None):
    f = Path(out or OUT) / jid / "denetci_raporu.md"
    if not f.exists():
        return None
    t = _n(f.read_text(encoding="utf-8-sig", errors="replace"))
    m = re.findall(r"denetci:\s*(gecti|kaldi)", t) or re.findall(r"\b(gecti|kaldi)\b", t)
    return m[-1] if m else None


def oku(item, out=None):
    d = Path(out or OUT) / item["id"]
    parca = []
    md, tp = d / "icerik_paketi.md", d / "tanitim_paketi.md"
    if md.exists():
        t = md.read_text(encoding="utf-8-sig", errors="replace")
        m = re.search(r"(?ms)^## U14[^\n]*\n(.*?)(?=^## |\Z)", t)
        if m:
            its = [re.sub(r"\s+", " ", x).strip() for x in re.split(r"(?m)^\s*\d\)\s*", m.group(1)) if x.strip()][:3]
            parca += [f"Gönderi {k}: {x[:240]}" for k, x in enumerate(its, 1)]
    elif tp.exists():
        t = tp.read_text(encoding="utf-8-sig", errors="replace")
        b = re.search(r"(?m)^\**BASLIK[^\n]*\n+\**([^\n]+)", t)
        k = re.search(r"(?m)^\**KISA ACIKLAMA[^\n]*\n+\**([^\n]+)", t)
        if b:
            parca.append("Mağaza başlığı: " + b.group(1).strip(" *")[:80])
        if k:
            parca.append("Kısa açıklama: " + k.group(1).strip(" *")[:160])
        rek = re.findall(r"(?m)^\**BA[SŞ]LIK:\**\s*([^\n]+)", t)[:3]
        if rek:
            parca.append("Reklam başlıkları: " + "; ".join(x.strip(" *")[:60] for x in rek))
    if not parca and (d / "OZET.txt").exists():
        return f"{_ad(item)}. " + re.sub(r"\s+", " ", (d / "OZET.txt").read_text(encoding="utf-8-sig", errors="replace")).strip()[:400]
    if not parca:
        return f"{_ad(item)} için okunacak metin dosyası bulunamadı."
    dd = denetci_durumu(item["id"], out)
    parca.append({"gecti": "Denetçi: geçti.", "kaldi": "Denetçi: SORUN buldu, dikkatle oku."}.get(dd, "Denetçi raporu yok."))
    return f"{_ad(item)}. " + " ".join(parca)


def paketler(items):
    if not items:
        return "Onay bekleyen paket yok."
    s = sorted(items, key=lambda i: i["mtime"], reverse=True)[:5]
    return (f"Onay bekleyen {len(items)} paket var: " +
            "; ".join(f"{k}) {_ad(i)}, saat {_saat(i)}" for k, i in enumerate(s, 1)) + ".")


def _pend_oku(p):
    return _j(p)


def _pend_yaz(p, d):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def karar(eylem, ifade, sebep="", evet=False, queue=None, onay=None, pend=None, out=None, simdi=None):
    queue, onay, pend = Path(queue or QUEUE), Path(onay or ONAYLAR), Path(pend or PEND)
    simdi = time.time() if simdi is None else simdi
    item, mesaj = paket_coz(ifade, bekleyenler(queue))
    if not item:
        return mesaj
    fiil = "onaylanacak" if eylem == "onayla" else "reddedilecek"
    if eylem == "reddet" and not sebep.strip():
        return f"{_ad(item)} reddedilecek. Kısa bir sebep söyler misin? Sonraki üretimde hatırlarım."
    p = _pend_oku(pend)
    ayni = p.get("id") == item["id"] and p.get("eylem") == eylem
    if evet:
        gecen = simdi - float(p.get("zaman", 0) or 0)
        if not ayni:
            evet = False
        elif gecen < BEKLE_MIN:
            return "Önce kullanıcının kendi sesiyle evet demesini bekle, sonra tekrar dene."
        elif gecen > BEKLE_MAX:
            evet = False
    if evet:
        try:
            import kado_onay
            kado_onay.karar_ver(item["id"], "ONAYLANDI" if eylem == "onayla" else "REDDEDILDI",
                                sebep or p.get("sebep", ""), queue, onay)
        except SystemExit as e:
            return f"Kayıt yapılamadı: {e}"
        try:
            pend.unlink()
        except Exception:
            pass
        return (f"{_ad(item)} {'onaylandı' if eylem == 'onayla' else 'reddedildi'}. "
                "Sadece kayıt yapıldı, hiçbir şey yayınlanmadı. Yanlışsa 'son kararı geri al' de.")
    uyari = ""
    if eylem == "onayla" and denetci_durumu(item["id"], out) == "kaldi":
        uyari = " Dikkat: denetçi bu pakette sorun bulmuştu."
    _pend_yaz(pend, {"id": item["id"], "eylem": eylem, "sebep": sebep, "zaman": simdi})
    return f"{_ad(item)} {fiil}.{uyari} Doğruysa 'evet' de."


def geri_al(ifade="son", queue=None, onay=None, yayin_klasor=None, simdi=None):
    queue, onay = Path(queue or QUEUE), Path(onay or ONAYLAR)
    yk = Path(yayin_klasor or YAYIN)
    aday = []
    for k in sorted(onay.glob("*.json"), key=lambda p: p.stat().st_mtime) if onay.exists() else []:
        for suf in (".done", ".failed"):
            if (queue / (k.stem + suf)).exists():
                aday.append((k, suf))
    if not aday:
        return "Geri alınacak karar yok."
    q = _n(ifade)
    if q in ("", "son", "son karar", "sonuncu"):
        sec = aday[-1]
    else:
        m = [a for a in aday if q in a[0].stem or (q in _n(_proje_adi(str(_j(queue / (a[0].stem + a[1])).get("goal", "")))))]
        if len(m) != 1:
            return "Hangi kararı geri alayım? 'son kararı geri al' de."
        sec = m[0]
    k, suf = sec
    if (queue / (k.stem + ".review")).exists():
        return "Bu paket zaten onay bekliyor."
    (queue / (k.stem + suf)).rename(queue / (k.stem + ".review"))
    arsiv = onay / "geri_alinan"
    arsiv.mkdir(exist_ok=True)
    shutil.move(str(k), str(arsiv / (k.stem + "_" + datetime.datetime.now().strftime("%H%M%S") + ".json")))
    j = _j(queue / (k.stem + ".review"))
    s = f"{_proje_adi(str(j.get('goal', ''))) or 'Paket'} kararı geri alındı, paket yeniden onay bekliyor."
    if (yk / k.stem).exists():
        s += " Yayın klasöründe hazırlanmış kopyası var, istersen elle sil."
    return s


# ---------------------------------------------------------------- sesle proje ekleme
def _yaz_projeler(dosya, liste):
    dosya = Path(dosya)
    dosya.parent.mkdir(parents=True, exist_ok=True)
    if dosya.exists():
        shutil.copy2(dosya, dosya.with_name(dosya.name + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")))
    tmp = dosya.with_suffix(".tmp")
    tmp.write_text(json.dumps(liste, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(dosya)


def _oku_projeler_siki(dosya):
    dosya = Path(dosya)
    if not dosya.exists():
        return []
    v = json.loads(dosya.read_text(encoding="utf-8-sig"))
    if not isinstance(v, list):
        raise ValueError("liste degil")
    return v


def proje_ekle(ad, hedef, platform="instagram", guncelle=False, dosya=None):
    dosya = Path(dosya or PROJELER)
    ad, hedef = str(ad).strip(), str(hedef).strip()
    if not (2 <= len(ad) <= 40) or _n(ad) in YER_TUTUCU or _n(ad).startswith("buraya"):
        return "Proje adı geçersiz. Gerçek bir proje adı söyler misin?"
    if len(hedef) < 25 or len(hedef.split()) < 5 or _n(hedef) in ("kisa hedef",) or _n(hedef).startswith("buraya"):
        return "Hedef çok kısa. Neyi, kime, nasıl bir dille anlatacağımızı bir iki cümleyle söyler misin?"
    try:
        from kado_icerik_hatti import YASAK
        y = YASAK.search(hedef)
        if y:
            return f"Hedefte yanıltıcı gelir vaadi var ('{y.group(0)}'). Neyi sunduğunu vaatsiz anlat."
    except ImportError:
        pass
    pl = _n(platform) if _n(platform) in PLATFORMLAR else "instagram"
    try:
        liste = _oku_projeler_siki(dosya)
    except Exception:
        return "projeler.json okunamadı, bu yüzden dokunmadım. Dosyayı kontrol etmem lazım."
    mevcut = next((p for p in liste if isinstance(p, dict) and _n(p.get("ad", "")) == _n(ad)), None)
    if mevcut and not guncelle:
        return f"{mevcut.get('ad')} zaten kayıtlı. Hedefi güncellememi istiyorsan 'güncelle' de."
    if mevcut:
        mevcut["hedef"], mevcut["platform"] = hedef, pl
        _yaz_projeler(dosya, liste)
        return f"{mevcut.get('ad')} projesinin hedefi güncellendi."
    liste.append({"ad": ad, "hedef": hedef, "platform": pl})
    _yaz_projeler(dosya, liste)
    return f"{ad} projesi eklendi. İstersen şimdi içerik hazırlatayım."


def proje_liste(dosya=None):
    try:
        liste = _oku_projeler_siki(dosya or PROJELER)
    except Exception:
        return "projeler.json okunamadı."
    adlar = [p.get("ad", "") for p in liste if isinstance(p, dict) and p.get("ad")]
    gercek = [a for a in adlar if _n(a) not in YER_TUTUCU and not _n(a).startswith("buraya")]
    if not adlar:
        return "Kayıtlı proje yok."
    s = "Kayıtlı projeler: " + ", ".join(gercek) + "." if gercek else "Gerçek proje yok."
    if len(gercek) < len(adlar):
        s += f" ({len(adlar) - len(gercek)} yer tutucu kayıt var; proje-sil ile temizlenebilir.)"
    return s


def proje_sil(ad, dosya=None):
    dosya = Path(dosya or PROJELER)
    try:
        liste = _oku_projeler_siki(dosya)
    except Exception:
        return "projeler.json okunamadı, dokunmadım."
    yeni = [p for p in liste if not (isinstance(p, dict) and _n(p.get("ad", "")) == _n(ad))]
    if len(yeni) == len(liste):
        return "Bu isimde proje yok."
    _yaz_projeler(dosya, yeni)
    return f"{ad} projesi silindi ({len(liste) - len(yeni)} kayıt)."


def gorev(istek, proje=None):
    try:
        import kado_ceo
    except ImportError:
        return "Genel müdür dosyası (kado_ceo.py) bulunamadı."
    return kado_ceo.ceo_calistir(istek, proje)


# ---------------------------------------------------------------- selftest
def selftest():
    import tempfile, os
    sys.path.insert(0, str(ROOT))
    with tempfile.TemporaryDirectory() as t:
        t = Path(t); q = t / "q"; o = t / "o"; a = t / "a"; pend = t / "pend.json"; yk = t / "yayin"
        q.mkdir(); o.mkdir()

        def mk(jid, kind, goal, mt, metin=None, ad="icerik_paketi.md"):
            f = q / f"{jid}.review"
            f.write_text(json.dumps({"id": jid, "kind": kind, "goal": goal}), encoding="utf-8")
            os.utime(f, (mt, mt))
            (o / jid).mkdir(exist_ok=True)
            if metin:
                (o / jid / ad).write_text(metin, encoding="utf-8-sig")
        mk("20261111_100000_aaa111", "icerik", "Han Toys: oyuncak", 1000,
           "# x\n## U14 - Gonderi\n1) Birinci metin burada.\n2) Ikinci metin.\n3) Ucuncu metin.\n## U15 - y\nz")
        mk("20261111_110000_bbb222", "icerik", "Han Toys: oyuncak2", 2000)
        mk("20261111_120000_ccc333", "tanitim", "KADO: tanitim paketi (cikis-oncesi)", 3000,
           "# T\n## Magaza\nBASLIK (en fazla 30 karakter)\nKADO: Ozel Asistan\n\nKISA ACIKLAMA (80)\nKullanici ozel asistani\n")
        it = bekleyenler(q)
        assert len(it) == 3
        assert paket_coz("kado", it)[0]["id"].endswith("ccc333")
        assert paket_coz("Han Toys", it)[0] is None and "2 paket" in paket_coz("Han Toys", it)[1]
        assert paket_coz("han toys en yeni", it)[0]["id"].endswith("bbb222")
        assert paket_coz("aaa111", it)[0]["id"].endswith("aaa111")
        assert paket_coz("son", it)[0]["id"].endswith("ccc333")
        assert paket_coz("yok boyle", it)[0] is None
        assert "Gönderi 1: Birinci" in oku(it[0], o) and "Denetçi raporu yok" in oku(it[0], o)
        assert "Mağaza başlığı: KADO: Ozel Asistan" in oku(it[2], o)
        (o / "20261111_120000_ccc333" / "denetci_raporu.md").write_text("DENETCI: KALDI", encoding="utf-8")
        assert denetci_durumu("20261111_120000_ccc333", o) == "kaldi"
        assert "Onay bekleyen 3 paket" in paketler(it)
        # iki adimli onay
        K = dict(queue=q, onay=a, pend=pend, out=o)
        r = karar("onayla", "kado", "", False, simdi=1000, **K)
        assert "onaylanacak" in r and "denetçi" in r and (q / "20261111_120000_ccc333.review").exists()
        assert "bekle" in karar("onayla", "kado", "", True, simdi=1001, **K)
        assert (q / "20261111_120000_ccc333.review").exists()
        assert "doğruysa" in karar("onayla", "aaa111", "", True, simdi=1010, **K).lower()
        assert (q / "20261111_100000_aaa111.review").exists() and not (q / "20261111_100000_aaa111.done").exists()
        _pend_yaz(pend, {"id": "20261111_120000_ccc333", "eylem": "onayla", "sebep": "", "zaman": 1000})
        assert "onaylandı" in karar("onayla", "kado", "", True, simdi=1010, **K)
        assert (q / "20261111_120000_ccc333.done").exists() and (a / "20261111_120000_ccc333.json").exists()
        assert "sebep" in karar("reddet", "aaa111", "", False, simdi=2000, **K)
        karar("reddet", "aaa111", "zayif metin", False, simdi=2000, **K)
        assert "reddedildi" in karar("reddet", "aaa111", "zayif metin", True, simdi=2010, **K)
        assert (q / "20261111_100000_aaa111.failed").exists()
        _pend_yaz(pend, {"id": "20261111_110000_bbb222", "eylem": "onayla", "sebep": "", "zaman": 1000})
        assert "onaylandı" not in karar("onayla", "bbb222", "", True, simdi=1000 + 500, **K)   # 180 sn gecti
        assert "geri alındı" in geri_al("son", q, a, yk)
        assert len(list(q.glob("*.review"))) == 2 and (a / "geri_alinan").exists()
        # proje ekleme
        pj = t / "projeler.json"
        assert "geçersiz" in proje_ekle("PROJE ADI", "Cocuklar icin egitici oyuncaklar anlat sade dille", dosya=pj)
        assert "kısa" in proje_ekle("Han Toys", "oyuncak", dosya=pj)
        assert "vaadi" in proje_ekle("Para", "Insanlara kolay para kazan yolunu anlat hemen simdi", dosya=pj)
        assert "eklendi" in proje_ekle("Han Toys", "Okul oncesi cocuklar icin egitici oyuncaklar, ebeveynlere sade anlat", dosya=pj)
        assert "zaten" in proje_ekle("han toys", "Okul oncesi cocuklar icin egitici oyuncaklar, ebeveynlere sade anlat", dosya=pj)
        assert "güncellendi" in proje_ekle("Han Toys", "Yeni hedef metni, daha uzun ve acik bir aciklama yazildi", "tiktok", True, dosya=pj)
        assert json.loads(pj.read_text(encoding="utf-8"))[0]["platform"] == "tiktok"
        assert len(list(t.glob("projeler.json.bak-*"))) >= 1
        assert "Han Toys" in proje_liste(pj)
        pj.write_text("{bozuk", encoding="utf-8")
        assert "dokunmadım" in proje_ekle("Yeni", "Bu yeterince uzun bir hedef metni olarak yazildi simdi", dosya=pj)
        assert pj.read_text(encoding="utf-8") == "{bozuk"
        pj.write_text('[{"ad":"PROJE ADI","hedef":"x"},{"ad":"Han Toys","hedef":"y"}]', encoding="utf-8")
        assert "yer tutucu" in proje_liste(pj) and "silindi" in proje_sil("proje adi", pj) and "yer tutucu" not in proje_liste(pj)
    print("SELFTEST 33/33 BASARILI: paket cozme, okuma, iki adimli onay/red, zaman siniri, geri alma, proje ekleme/koruma")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = sys.argv[1:]

    def bayrak(ad):
        if ad in a:
            a.remove(ad)
            return True
        return False

    def deger(ad, varsayilan=""):
        if ad in a:
            i = a.index(ad)
            v = a[i + 1] if i + 1 < len(a) else varsayilan
            del a[i:i + 2]
            return v
        return varsayilan
    try:
        if not a:
            print(__doc__)
        elif a[0] == "selftest":
            selftest()
        elif a[0] == "baslat":
            yen = bayrak("--yeniden")
            print(baslat(" ".join(x for x in a[1:]), yen))
        elif a[0] == "durum":
            print(durum())
        elif a[0] == "yayin":
            print(yayin())
        elif a[0] == "paketler":
            print(paketler(bekleyenler()))
        elif a[0] == "oku":
            it, m = paket_coz(" ".join(a[1:]), bekleyenler())
            print(oku(it) if it else m)
        elif a[0] in ("onayla", "reddet"):
            ev = bayrak("--evet")
            r = a[1:]
            print(karar(a[0], r[0] if r else "son", " ".join(r[1:]) if a[0] == "reddet" else "", ev))
        elif a[0] == "geri":
            print(geri_al(" ".join(a[1:]) or "son"))
        elif a[0] == "proje-ekle":
            pl = deger("--platform", "instagram")
            gu = bayrak("--guncelle")
            print(proje_ekle(a[1] if len(a) > 1 else "", a[2] if len(a) > 2 else "", pl, gu))
        elif a[0] == "proje-liste":
            print(proje_liste())
        elif a[0] == "proje-sil":
            print(proje_sil(" ".join(a[1:])))
        elif a[0] == "gorev":
            pr = deger("--proje", "")
            print(gorev(" ".join(a[1:]), pr or None))
        else:
            print("Bilinmeyen komut. Kullanim icin: python kado_ses_icerik_koprusu.py")
    except Exception as e:
        print("Hata: " + str(e)[:150])
