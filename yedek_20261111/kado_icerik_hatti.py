"""KADO icerik hatti V4: metin -> gorsel fikri -> hashtag -> 7 gunluk takvim -> rapor.
Yerel Ollama kullanir (ucretsiz). Hicbir hesapta YAYIN YAPMAZ, internete cikmaz, kod calistirmaz.
Sonuc kuyruga 'review' olarak girer: insan onayi gerekir.
Kullanim: python kado_icerik_hatti.py "GERCEK PROJE ADI" "gercek hedef" [--platform instagram]
         python kado_icerik_hatti.py selftest
V4: her adim tek isle sinirli ve KOD ile dogrulanir; hatali cikti 1 kez daha denenir, olmazsa 'eksik' sayilir.
Dogrulamalar: sablon metni kopyalama, tekrar eden metin/hashtag/konu, kesilen cikti, 7 gunden eksik takvim,
'kolay para / garantili kazanc / pasif gelir' gibi yaniltici gelir vaatleri.
"""
import argparse, datetime, json, os, pathlib, re, secrets, sys, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
BASE = ROOT / "kado_agent_motor"
QUEUE = BASE / "kuyruk"
OUT = BASE / "ciktilar"
MODEL = os.getenv("KADO_ICERIK_MODEL", "qwen3:8b")
URL = os.getenv("KADO_OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
NUM_PREDICT = int(os.getenv("KADO_ICERIK_TOKEN", "2200"))
ENC = "utf-8-sig"

YASAK = re.compile(
    r"(kolay|kolayca|h[ıi]zl[ıi]|garantili|kesin|risksiz|zahmetsiz)\s+(para|kazan|gelir|zengin)"
    r"|zengin\s+ol|pasif\s+gelir|(kazan[cç]|gelir)\s+garanti", re.I)


def llm(prompt):
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False, "think": False,
                       "options": {"temperature": 0.6, "num_predict": NUM_PREDICT}}).encode("utf-8")
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.load(r)
    metin = re.sub(r"<think>.*?</think>", "", d.get("response", ""), flags=re.S).strip()
    return metin, d.get("done_reason", "")


def adim(ad, prompt, gen, kontrol=None, tekrar="", min_uzun=80):
    """(metin, hata). Hata varsa adim eksik sayilir. Kontrol basarisizsa 1 kez daha dener."""
    def bir(pr):
        try:
            res = gen(pr)
        except Exception as e:
            return None, f"{ad}: HATA {type(e).__name__} (Ollama calisiyor mu? model yuklu mu?)", False, ""
        metin, neden = res if isinstance(res, tuple) else (res, "")
        metin = (metin or "").strip()
        if len(metin) < min_uzun:
            return None, f"{ad}: cikti cok kisa ({len(metin)} karakter), gecersiz sayildi", False, ""
        if neden == "length":
            return metin, f"{ad}: cikti KESILDI (token siniri), eksik sayildi", False, ""
        if kontrol:
            m = kontrol(metin)
            if m:
                return metin, f"{ad}: {m}", True, m
        return metin, None, False, ""
    metin, hata, tekrar_edilebilir, sorun = bir(prompt)
    if hata and tekrar_edilebilir and tekrar:
        metin2, hata2, _, _ = bir(prompt + "\n\n" + tekrar + " Sorun: " + sorun)
        if not hata2:
            return metin2, None
        return (metin2 or metin), (hata2 + " (2. denemede de)")
    return metin, hata


def maddeler(metin):
    return [p.strip() for p in re.split(r"(?m)^\s*\d\)\s*", metin) if p.strip()]


def vaat_kontrol(metin):
    y = YASAK.search(metin)
    return f"yaniltici gelir/kolay para vaadi iceriyor: '{y.group(0)}'" if y else None


def u14_kontrol(m):
    it = maddeler(m)
    if len(it) < 3:
        return f"3 metin yok ({len(it)} bulundu)"
    if len({x.lower() for x in it[:3]}) < 3:
        return "metinler birbirinin ayni"
    return vaat_kontrol(m)


def u15_gorsel_kontrol(m):
    it = maddeler(m)
    if len(it) < 3:
        return f"3 gorsel fikri yok ({len(it)} bulundu)"
    if "<" in m or ">" in m:
        return "sablon/yer tutucu metni aynen kopyalanmis"
    if any(len(x) < 25 for x in it[:3]):
        return "gorsel fikri cok kisa"
    if len({x.lower() for x in it[:3]}) < 3:
        return "gorsel fikirleri birbirinin ayni"
    return vaat_kontrol(m)


def etiketler(m):
    gor = []
    for t in re.findall(r"#\w+", m):
        if t.lower() not in [g.lower() for g in gor]:
            gor.append(t)
    return gor[:8]


def u15_etiket_kontrol(m):
    n = len(etiketler(m)) if len(re.findall(r"#\w+", m)) else 0
    tum = {t.lower() for t in re.findall(r"#\w+", m)}
    return None if len(tum) >= 8 else f"8 farkli hashtag yok ({len(tum)} farkli bulundu)"


def takvim_kontrol(m):
    s = re.findall(r"(?mi)^\s*g[uü]n\s*(\d)\s*\|\s*([^|\n]+?)\s*\|\s*([^|\n]+?)\s*\|\s*(\S[^|\n]*)$", m)
    if len(s) < 7:
        return f"takvim 7 gunden eksik ({len(s)} gun bulundu)"
    if len({x[2].strip().lower() for x in s}) < 6:
        return "gunlerin konulari ayni, tekrar ediyor"
    if len({x[1].strip().lower() for x in s}) < 2:
        return "takvimde tek format var"
    return vaat_kontrol(m)


def calistir(proje, hedef, platform, gen=llm, out=OUT, queue=QUEUE):
    jid = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_") + secrets.token_hex(3)
    d = out / jid
    d.mkdir(parents=True, exist_ok=True)
    queue.mkdir(parents=True, exist_ok=True)
    ctx = f"Proje adi: {proje}\nHedef: {hedef}\nPlatform: {platform}\n"
    kural = ("Turkce yaz. SADECE yukaridaki proje adi ve hedefte yazan bilgileri kullan. "
             "Kampanya, indirim, odul, surpriz, kisi sayisi, fiyat, tarih, kitle yasi veya rakam UYDURMA; "
             "hedefte yoksa yazma. Proje adini aynen kullan. Abartili vaat verme. "
             "Gelir, kazanc veya kolay para vaadi YAZMA (kolay para, garantili kazanc, hizli zengin olma, "
             "pasif gelir gibi). Hedefte yazan bir faydayi abartmadan, dogrudan anlat.\n")
    T = ("ONEMLI: Onceki cevap istenen bicimde degildi. Talimata AYNEN uy: sablon veya yer tutucu "
         "metni kopyalama, ayni seyi tekrar etme, gelir/kolay para vaadi yazma.")
    hatalar, sonuc = [], {}

    def calis(kod, prompt, kontrol, min_uzun=80):
        if hatalar:
            hatalar.append(f"{kod}: onceki adim eksik oldugu icin calistirilmadi")
            return None
        m, h = adim(kod, prompt, gen, kontrol, T, min_uzun)
        if h:
            hatalar.append(h)
        return m

    u14 = calis("U14", "Rol: sosyal medya metin yazari.\n" + ctx + kural +
                "3 FARKLI gonderi metni yaz. Her biri en fazla 50 kelime, sonunda net bir cagri olsun. "
                "Numarala: 1), 2), 3). Baska aciklama yazma.", u14_kontrol)
    gorsel = calis("U15-gorsel", "Rol: sosyal medya uzmani.\n" + ctx + kural +
                   "Asagidaki 3 gonderi metni icin birer gorsel veya kisa video fikri yaz. Her fikir en fazla "
                   "2 cumle olsun, sahneyi anlat, gonderi metnini tekrar etme. Numarala: 1), 2), 3). "
                   "Baska aciklama yazma.\n\nMETINLER:\n" + (u14 or ""), u15_gorsel_kontrol)
    etiket = calis("U15-hashtag", "Rol: sosyal medya uzmani.\n" + ctx + kural +
                   "Bu proje icin 8 FARKLI hashtag yaz. Tek satirda, bosluk ile ayir, her biri # ile baslasin, "
                   "hicbirini tekrar etme. Baska aciklama yazma.", u15_etiket_kontrol, 20)
    takvim = calis("U16", "Rol: yayin planlayici.\n" + ctx + kural +
                   "7 gunluk yayin takvimi yaz. TAM 7 satir, her satir su bicimde: Gun N | format | konu | saat. "
                   "Her gunun konusu FARKLI olsun, ayni konuyu tekrar etme. Formati gonderi, reel ve hikaye "
                   "arasinda degistir. Baska aciklama yazma. Bu sadece taslaktir, otomatik yayin yoktur.",
                   takvim_kontrol)

    sonuc["U14"] = u14
    if gorsel:
        parca = [f"METIN {i}: {x}" for i, x in enumerate(maddeler(gorsel)[:3], 1)]
        if etiket:
            parca.append("HASHTAG: " + " ".join(etiketler(etiket)))
        sonuc["U15"] = "\n".join(parca)
    sonuc["U16"] = takvim

    tamam = not hatalar and all(sonuc.get(k) for k in ("U14", "U15", "U16"))
    rapor = [f"# KADO Icerik Paketi: {proje}", f"Gorev: {jid}", f"Hedef: {hedef}", f"Platform: {platform}",
             f"Model: {MODEL} (yerel; kaliteyi insan gozuyle kontrol et)", ""]
    for k, baslik in (("U14", "Gonderi metinleri"), ("U15", "Gorsel fikirleri ve hashtag"), ("U16", "7 gunluk takvim")):
        rapor += [f"## {k} - {baslik}", sonuc.get(k) or "(uretilemedi)", ""]
    if hatalar:
        rapor += ["## Hatalar"] + [f"- {x}" for x in hatalar] + [""]
    rapor += ["## Durum", "YAYINLANMADI. Bu taslak insan onayi bekler."]
    (d / "icerik_paketi.md").write_text("\n".join(rapor), encoding=ENC)
    (d / "ONAY_GEREKLI.txt").write_text("Bu icerik hicbir hesapta yayinlanmadi. Onay vermeden yayinlanmaz.\n", encoding=ENC)
    # V4 gorev merkezi 'review' dosyalarini okur; V3 isci sadece .json alir, uretim motoruna girmez.
    (queue / f"{jid}.review").write_text(json.dumps(
        {"id": jid, "kind": "icerik", "goal": f"{proje}: {hedef}"[:2000]}, ensure_ascii=False), encoding="utf-8")
    return jid, d, tamam, hatalar


def selftest():
    import tempfile
    u14_iyi = "\n".join(f"{i}) Bu {i}. gonderi metni, projeyi sade ve net anlatan yeterince uzun bir cumledir." for i in range(1, 4))
    gorsel_iyi = "\n".join(f"{i}) Masanin ustunde {i}. sahne: yakin cekim bir urun ve gulumseyen bir kisi." for i in range(1, 4))
    etiket_iyi = "#a1 #b2 #c3 #d4 #e5 #f6 #g7 #h8"
    gunler_iyi = "\n".join(f"Gun {i} | {'reel' if i % 2 else 'gonderi'} | konu numarasi {i} | 10:00" for i in range(1, 8))

    def iyi(p):
        if "metin yazari" in p: return u14_iyi
        if "gorsel veya kisa video" in p: return gorsel_iyi
        if "hashtag yaz" in p: return etiket_iyi
        return gunler_iyi

    def kotu_ilk(anahtar, kotu, hep=False):
        n = {"c": 0}
        def g(p):
            if anahtar in p:
                n["c"] += 1
                if hep or "ONEMLI" not in p:
                    return kotu
            return iyi(p)
        g.n = n
        return g

    with tempfile.TemporaryDirectory() as t:
        t = pathlib.Path(t)
        run = lambda g: calistir("Test", "deneme", "instagram", g, t / "o", t / "q")
        jid, d, tamam, h = run(iyi)
        assert tamam and not h
        md = (d / "icerik_paketi.md").read_text(encoding=ENC)
        assert "YAYINLANMADI" in md and "HASHTAG:" in md and (d / "ONAY_GEREKLI.txt").exists()
        job = json.loads((t / "q" / f"{jid}.review").read_text(encoding="utf-8"))
        assert job["id"] == jid and job["kind"] == "icerik"
        assert not run(lambda p: "kisa")[2]
        _, _, tk, hk = run(lambda p: (iyi(p), "length"))
        assert not tk and any("KESILDI" in x for x in hk)
        vaat = "1) Kolay para kazan, hemen katil ve hemen basla.\n2) Kolayca para kazanmak icin tikla bugun.\n3) Garantili kazanc seni bekliyor hemen.\n"
        g = kotu_ilk("metin yazari", vaat)
        assert run(g)[2] and g.n["c"] == 2
        _, _, tv, hv = run(kotu_ilk("metin yazari", vaat, hep=True))
        assert not tv and any("2. denemede de" in x for x in hv)
        sablon = "\n".join(f"{i}) <sahneyi tarif et, gonderi metnini tekrar yazma> ve baska uzun bir yazi" for i in range(1, 4))
        g = kotu_ilk("gorsel veya kisa video", sablon)
        assert run(g)[2] and g.n["c"] == 2
        g = kotu_ilk("hashtag yaz", "#a #a #a #b #b #b #c #c #c #c")
        assert run(g)[2] and g.n["c"] == 2
        tek_konu = "\n".join(f"Gun {i} | reel | ayni konu | 10:00" for i in range(1, 8))
        _, _, ts, hs = run(kotu_ilk("yayin planlayici", tek_konu, hep=True))
        assert not ts and any("konulari ayni" in x for x in hs)
    print("SELFTEST 9/9 BASARILI: uretim, kuyruk, kisa, kesik, vaat (duzeltme + red), sablon, hashtag, takvim")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        return selftest()
    ap = argparse.ArgumentParser()
    ap.add_argument("proje"); ap.add_argument("hedef"); ap.add_argument("--platform", default="instagram")
    a = ap.parse_args()
    if (a.proje.strip().upper() in ("PROJE ADI", "GERCEK PROJE ADI") or a.proje.strip().upper().startswith("BURAYA")
            or a.hedef.strip().lower() in ("kısa hedef", "kisa hedef") or a.hedef.strip().upper().startswith("BURAYA")):
        print("DURDURULDU: Gercek proje adi ve hedef yaz. Yer tutucu metinle calismaz.")
        return 2
    jid, d, tamam, hatalar = calistir(a.proje, a.hedef, a.platform)
    print("GOREV:", jid)
    print("CIKTI:", d / "icerik_paketi.md")
    print("DURUM:", "TAMAMLANDI - YAYINLANMADI, ONAY GEREKLI" if tamam else "EKSIK - hatalara bak")
    for x in hatalar:
        print("HATA:", x)
    return 0 if tamam else 1


if __name__ == "__main__":
    sys.exit(main())
