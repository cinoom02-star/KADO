# -*- coding: utf-8 -*-
"""KADO DENETCI (U18 Kalite Kontrolcu).
Uretilen paketi once KODLA, sonra yerel modelle denetler. Sorun varsa ilgili bolumu
nedenleriyle yeniden yazdirir (en fazla KADO_DENETCI_TUR=2 tur), sonra sana birakir.
Paket bicimi korunur (kart/video betikleri okuyor). Orijinal: icerik_paketi.v0.md.
Hicbir seyi yayinlamaz, onaylamaz. Rapor: denetci_raporu.md
Kullanim:
  python kado_denetci.py GOREV_ID [--tur N] [--sadece-kontrol] [--hedef "aciklama"]
  python kado_denetci.py selftest
"""
import sys, re, os, json, shutil, argparse, tempfile, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "kado_agent_motor" / "ciktilar"
ENC = "utf-8-sig"
MAX_TUR = int(os.getenv("KADO_DENETCI_TUR", "2"))

KURAL = ("Turkce yaz. SADECE yukaridaki proje adi ve hedefte yazan bilgileri kullan. "
         "Kampanya, indirim, odul, surpriz, kisi sayisi, fiyat, tarih, kitle yasi veya rakam UYDURMA; "
         "hedefte yoksa yazma. Proje adini aynen kullan. Abartili vaat verme. "
         "Gelir, kazanc veya kolay para vaadi YAZMA (kolay para, garantili kazanc, hizli zengin olma, "
         "pasif gelir gibi). Hedefte yazan bir faydayi abartmadan, dogrudan anlat.\n")
TEKRAR = ("ONEMLI: Onceki cevap istenen bicimde degildi. Talimata AYNEN uy: sablon veya yer tutucu "
          "metni kopyalama, ayni seyi tekrar etme, gelir/kolay para vaadi yazma.")

# hedefte (ya da proje adinda) gecmiyorsa iddia sayilan kok kelimeler (norm bicimi)
IDDIA = ("guven", "kalite", "zihinsel", "gelisim", "sertifika", "uzman", "onayli", "ucretsiz", "indirim",
         "kampanya", "saglik", "bilimsel", "kanitlan", "yerli", "organik", "toksik", "en iyi", "odullu",
         "ozel tasar", "garanti")
TON = {"sade", "samimi", "dil", "uslup", "ton", "abartisiz"}   # talimat kelimeleri hashtag olmasin


def norm(s):
    s = str(s).replace("İ", "i").replace("I", "ı").lower()
    return s.translate(str.maketrans("çğıöşüâîû", "cgiosuaiu"))


def maddeler(metin):
    return [p.strip() for p in re.split(r"(?m)^\s*\d\)\s*", metin) if p.strip()]


def toks(s):
    return {w for w in re.findall(r"[a-z0-9]+", norm(s)) if len(w) > 3}


def jacc(a, b):
    ta, tb = toks(a), toks(b)
    return len(ta & tb) / max(1, len(ta | tb))


def iddia_kontrol(metin, izinli, yer):
    n = " " + norm(metin)
    out = []
    for k in IDDIA:
        kk = (" " + k) if " " in k else k
        if kk in n and k not in izinli:
            out.append(f"hedefte olmayan iddia: '{k}' ({yer})")
    return out


# ---------- ICERIK PAKETI ----------
def _sec_re(k):
    return re.compile(r"(?ms)^(## %s - [^\n]*\n)(.*?)(?=^## |\Z)" % re.escape(k))


def bolum_oku(md, k):
    m = _sec_re(k).search(md)
    return m.group(2).strip() if m else ""


def bolum_yaz(md, k, yeni):
    return _sec_re(k).sub(lambda m: m.group(1) + yeni.strip() + "\n\n", md, count=1)


def icerik_oku(md):
    g = lambda pat: (re.search(pat, md) or [None, ""])[1].strip() if re.search(pat, md) else ""
    hedef_full = g(r"(?m)^Hedef:\s*(.+)$")
    u15 = bolum_oku(md, "U15")
    gorsel = re.findall(r"(?m)^METIN\s*\d+:\s*(.+)$", u15)
    th = re.search(r"(?m)^HASHTAG:\s*(.*)$", u15)
    return {"proje": g(r"(?m)^# KADO Icerik Paketi:\s*(.+)$"), "hedef_full": hedef_full,
            "hedef": hedef_full.split(" | HAFIZA:")[0].strip(), "platform": g(r"(?m)^Platform:\s*(.+)$") or "instagram",
            "U14": bolum_oku(md, "U14"), "gorsel": gorsel,
            "tags": re.findall(r"#\w+", th.group(1)) if th else [], "U16": bolum_oku(md, "U16")}


def kontrol_icerik(p):
    sor = []
    izinli = norm(p["hedef"] + " " + p["proje"])
    items = maddeler(p["U14"])
    for i, it in enumerate(items[:3], 1):
        if norm(p["proje"]) not in norm(it):
            sor.append(("U14", f"metin {i} proje adini ({p['proje']}) icermiyor"))
        n = len(it.split())
        if n > 60:
            sor.append(("U14", f"metin {i} cok uzun ({n} kelime, en fazla 50)"))
    sor += [("U14", m) for m in iddia_kontrol(p["U14"], izinli, "gonderi metni")]
    for i, v in enumerate(p["gorsel"][:3], 1):
        if items and max(jacc(v, it) for it in items) >= 0.5:
            sor.append(("U15g", f"gorsel fikri {i} gonderi metnini tekrar ediyor, sahne anlatmiyor"))
    sor += [("U15g", m) for m in iddia_kontrol(" ".join(p["gorsel"]), izinli, "gorsel fikri")]
    for t in p["tags"]:
        kel = re.sub(r"(?<=[a-zçğıöşü0-9])(?=[A-ZÇĞİÖŞÜ])", " ", t.lstrip("#")).split()
        if any(norm(w) in TON for w in kel):
            sor.append(("U15h", f"hashtag ton talimatina benziyor: {t}"))
    sor += [("U15h", m) for m in iddia_kontrol(" ".join(p["tags"]), izinli, "hashtag")]
    sor += [("U16", m) for m in iddia_kontrol(p["U16"], izinli, "takvim")]
    return sor


def llm_prompt_icerik(p):
    return ("Rol: Turkce kalite kontrolcusu (denetci).\n"
            f"Proje: {p['proje']}\nHedef (tek gercek bilgi kaynagi): {p['hedef']}\n"
            "Asagidaki sosyal medya taslagini KATI incele ve sadece GERCEK, somut sorunlari bildir:\n"
            "- Dil bilgisi ve anlam: yanlis kisi eki, bozuk cumle, anlamsiz ifade\n"
            "- Hedefte olmayan iddia, ozellik veya fayda\n"
            "- Gorsel fikri gercek bir sahne mi, gonderi metnini tekrar mi ediyor\n"
            "- Hashtagler anlamli ve projeye ozgu mu\n"
            "Bicim (baska hicbir sey yazma):\nKARAR: GECTI veya KALDI\n"
            "SORUN: [METIN] kisa somut sorun   (etiket: [METIN], [GORSEL] veya [HASHTAG]; en fazla 5 satir)\n"
            "Sorun yoksa KARAR: GECTI yaz ve SORUN satiri yazma. Zevk meselesi veya genel tavsiye yazma.\n\n"
            "GONDERI METINLERI:\n" + p["U14"] + "\n\nGORSEL FIKIRLERI:\n" + "\n".join(p["gorsel"]) +
            "\n\nHASHTAGLER:\n" + " ".join(p["tags"]))


def parse_review(out, harita, varsayilan):
    n = norm(out)
    k = re.search(r"karar:\s*(gecti|kaldi)", n)
    sorunlar = []
    for s in re.findall(r"(?im)^\s*sorun\s*:\s*(.+)$", out):
        m = re.match(r"\[([A-Za-z]+)\]\s*(.*)", s.strip())
        etiket, metin = (m.group(1).upper(), m.group(2)) if m else ("", s.strip())
        if len(metin) >= 8:
            sorunlar.append((harita.get(etiket, varsayilan), "denetci: " + metin[:200]))
    if k and k.group(1) == "kaldi" and sorunlar:
        return sorunlar[:5]
    return []


def yaz_icerik(p, sor, gen, notlar):
    import kado_icerik_hatti as H
    ctx = f"Proje adi: {p['proje']}\nHedef: {p['hedef_full']}\nPlatform: {p['platform']}\n"
    by = {}
    for k, m in sor:
        by.setdefault(k, []).append(m)

    def fb(*keys):
        ms = [m for k in keys for m in by.get(k, [])]
        if not ms:
            return ""
        yasak = sorted({x for m in ms for x in re.findall(r"iddia: '([^']+)'", m)})
        s = "DENETCI GERI BILDIRIMI (bunlari DUZELT):\n" + "\n".join("- " + m for m in ms) + "\n"
        if yasak:
            s += "Su kelimeleri HIC KULLANMA: " + ", ".join(yasak) + ".\n"
        return s

    yeni = dict(p)
    if "U14" in by:
        pr = ("Rol: sosyal medya metin yazari.\n" + ctx + KURAL + fb("U14") +
              "3 FARKLI gonderi metni yaz. Her biri en fazla 50 kelime, sonunda net bir cagri olsun. "
              "Her metinde proje adini aynen kullan. Dogru ve akici Turkce kullan (kisi ekleri tutarli olsun). "
              "Numarala: 1), 2), 3). Baska aciklama yazma.")
        m, h = H.adim("U14", pr, gen, H.u14_kontrol, TEKRAR)
        if not h and m:
            yeni["U14"] = m
            notlar.append("U14 yeniden yazildi")
        else:
            notlar.append(f"U14 yeniden yazilamadi: {h}")
    if "U14" in by and yeni["U14"] != p["U14"] or "U15g" in by:
        pr = ("Rol: sosyal medya uzmani.\n" + ctx + KURAL + fb("U15g") +
              "Asagidaki 3 gonderi metni icin birer gorsel veya kisa video fikri yaz. Her fikir BIR SAHNE olsun "
              "(kim, nerede, ne yapiyor, ekranda ne gorunuyor), en fazla 2 cumle. Gonderi metnindeki cumleleri "
              "veya kelime gruplarini TEKRAR ETME. Numarala: 1), 2), 3). Baska aciklama yazma.\n\nMETINLER:\n" + yeni["U14"])
        m, h = H.adim("U15-gorsel", pr, gen, H.u15_gorsel_kontrol, TEKRAR)
        if not h and m:
            yeni["gorsel"] = maddeler(m)[:3]
            notlar.append("gorsel fikirleri yeniden yazildi")
        else:
            notlar.append(f"gorsel fikirleri yeniden yazilamadi: {h}")
    if "U15h" in by:
        pr = ("Rol: sosyal medya uzmani.\n" + ctx + KURAL + fb("U15h") +
              "Bu proje icin 8 FARKLI hashtag yaz. Tek satirda, bosluk ile ayir, her biri # ile baslasin, hicbirini "
              "tekrar etme. Hashtagler projeye ve konuya ozgu, anlamli olsun; ton veya uslup kelimesi (sade, samimi, "
              "dil gibi) icermesin. Baska aciklama yazma.")
        m, h = H.adim("U15-hashtag", pr, gen, H.u15_etiket_kontrol, TEKRAR, 20)
        if not h and m:
            yeni["tags"] = H.etiketler(m)
            notlar.append("hashtagler yeniden yazildi")
        else:
            notlar.append(f"hashtagler yeniden yazilamadi: {h}")
    if "U16" in by:
        pr = ("Rol: yayin planlayici.\n" + ctx + KURAL + fb("U16") +
              "7 gunluk yayin takvimi yaz. TAM 7 satir, her satir su bicimde: Gun N | format | konu | saat. "
              "Her gunun konusu FARKLI olsun. Formati gonderi, reel ve hikaye arasinda degistir. "
              "Baska aciklama yazma. Bu sadece taslaktir, otomatik yayin yoktur.")
        m, h = H.adim("U16", pr, gen, H.takvim_kontrol, TEKRAR)
        if not h and m:
            yeni["U16"] = m
            notlar.append("takvim yeniden yazildi")
        else:
            notlar.append(f"takvim yeniden yazilamadi: {h}")
    return yeni


def birlestir_icerik(md, p):
    md = bolum_yaz(md, "U14", p["U14"])
    u15 = [f"METIN {i}: {x}" for i, x in enumerate(p["gorsel"][:3], 1)]
    if p["tags"]:
        u15.append("HASHTAG: " + " ".join(p["tags"][:8]))
    md = bolum_yaz(md, "U15", "\n".join(u15))
    return bolum_yaz(md, "U16", p["U16"])


# ---------- TANITIM PAKETI ----------
def tanitim_bolumleri(md):
    out = []
    for m in re.finditer(r"(?ms)^## ([^\n]+)\n(.*?)(?=^## |\Z)", md):
        if m.group(1).strip() != "KONTROL":
            out.append((m.group(1).strip(), m.group(2).strip()))
    return out


def tanitim_oku(md):
    g = lambda pat: (re.search(pat, md).group(1).strip() if re.search(pat, md) else "")
    return {"ad": g(r"(?m)^# Tanitim paketi - (.+)$"), "asama": g(r"(?m)^Asama:\s*(\S+)") or "cikis-oncesi",
            "sec": tanitim_bolumleri(md)[:3]}


def sizinti_mi(satir):
    """Modelin metne karistirdigi kendi notu / talimat satiri mi?"""
    n = norm(satir)
    return bool(re.search(
        r"duzeltildi|yanlis kelimeler|hedefte olmayan iddia|henuz cikmadi ama|denetci geri bildirimi"
        r"|^[\s*\-]*(durum|kurallar|proje|aciklama)\s*:\**\s*(uygulama henuz|turkce yaz|proje:)|^\s*\u2192", n))


def temizle_yanit(metin):
    return "\n".join(l for l in str(metin).splitlines() if not sizinti_mi(l))


def kontrol_tanitim(t, hedef):
    import kado_tanitim_paketi as TP
    sor = []
    izinli = norm((hedef or "") + " " + t["ad"])
    for key, (baslik, body) in zip(("M", "I", "R"), t["sec"]):
        if "(uretilemedi" in body:
            continue
        n = norm(body)
        if any(sizinti_mi(l) for l in body.splitlines()):
            sor.append((key, f"modelin kendi notu/talimati metne karismis ({baslik})"))
        for y in TP.YASAK:
            if norm(y) in n:
                sor.append((key, f"yasakli ifade: '{y}' ({baslik})"))
        if hedef:
            sor += [(key, m) for m in iddia_kontrol(body, izinli, baslik)]
        if t["asama"] == "cikis-oncesi" and re.search(r"\bindir\b|\bindirin\b|\bindirebilirsin", n):
            sor.append((key, f"uygulama henuz cikmadi ama 'indir' diyor ({baslik})"))
        if re.search(r"\[[A-Za-z ]{2,15}\]", body):
            sor.append((key, f"yer tutucu kaldi, kose parantezli ifade ({baslik})"))
        satirlar = [re.sub(r"[*#\s]+", " ", x).strip().lower() for x in body.splitlines()]
        kopya = {x for x in satirlar if len(x) > 12 and satirlar.count(x) > 1}
        if kopya:
            sor.append((key, f"ayni satir birden fazla kez tekrar ediyor ({baslik})"))
        if key == "I" and re.search(r"(?m)\bisim\s*:", n):
            sor.append((key, f"gercek kisi gibi isim verilmis, sadece profil tipi yazilmali ({baslik})"))
        if key == "M":
            def ilk(bas):
                m = re.search(r"(?im)^%s[^\n]*\n\s*([^\n]+)" % bas, body)
                return m.group(1).strip() if m else ""
            for bas, lim in (("BASLIK", 30), ("KISA ACIKLAMA", 80)):
                v = ilk(bas)
                if v and len(v) > lim:
                    sor.append((key, f"{bas.lower()} {len(v)} karakter, en fazla {lim} ({baslik})"))
        if key == "R":
            for bas, lim in (("BASLIK", 40), ("GOVDE", 125)):
                for v in re.findall(r"(?im)^\W*%s\W*:\W*(.+)$" % bas, body):
                    v = re.sub(r"\*+", "", v).strip()
                    if len(v) > lim:
                        sor.append((key, f"reklam {bas.lower()} {len(v)} karakter, en fazla {lim} ({baslik})"))
    return sor


def llm_prompt_tanitim(t, hedef):
    s = ("Rol: Turkce kalite kontrolcusu (denetci).\n"
         f"Proje: {t['ad']}\nAciklama (tek gercek bilgi kaynagi): {hedef or '(verilmedi)'}\nAsama: {t['asama']}\n"
         "Asagidaki tanitim taslaginin 3 bolumunu KATI incele; sadece GERCEK, somut sorunlari bildir: "
         "dil bilgisi ve anlam bozuklugu, aciklamada olmayan iddia/ozellik/rakam, cikis oncesiyse 'indir' deme, "
         "baskici veya spam gibi mesaj.\nBicim (baska hicbir sey yazma):\nKARAR: GECTI veya KALDI\n"
         "SORUN: [MAGAZA] kisa somut sorun   (etiket: [MAGAZA], [INFLUENCER] veya [REKLAM]; en fazla 5 satir)\n"
         "Sorun yoksa KARAR: GECTI yaz ve SORUN satiri yazma.\n")
    for etiket, (baslik, body) in zip(("MAGAZA", "INFLUENCER", "REKLAM"), t["sec"]):
        s += f"\n[{etiket}] {baslik}:\n{body[:1500]}\n"
    return s


def yaz_tanitim(md, t, hedef, sor, gen, notlar):
    import kado_tanitim_paketi as TP
    prompts = TP.bolumler(t["ad"], hedef, t["asama"])
    by = {}
    for k, m in sor:
        by.setdefault(k, []).append(m)
    for key, idx in (("M", 0), ("I", 1), ("R", 2)):
        if key not in by or idx >= len(t["sec"]):
            continue
        baslik, prompt = prompts[idx]
        yasak = sorted({x for m in by[key] for x in re.findall(r"iddia: '([^']+)'", m)})
        fb = ("\n\nDENETCI GERI BILDIRIMI (bunlari DUZELT):\n" + "\n".join("- " + m for m in by[key]) +
              ("\nSu kelimeleri HIC KULLANMA: " + ", ".join(yasak) + "." if yasak else "") +
              "\nDogru ve akici Turkce kullan.")
        try:
            r = gen(prompt + fb)
            r = (r[0] if isinstance(r, tuple) else r or "").strip()
        except Exception as e:
            notlar.append(f"{baslik} yeniden yazilamadi: {type(e).__name__}")
            continue
        r = temizle_yanit(r).strip()
        if len(r) < TP.MIN_UZUNLUK:
            notlar.append(f"{baslik} yeniden yazilamadi: cikti cok kisa")
            continue
        md = re.sub(r"(?ms)^(## %s\n)(.*?)(?=^## |\Z)" % re.escape(t["sec"][idx][0]),
                    lambda m: m.group(1) + r + "\n\n", md, count=1)
        notlar.append(f"{baslik} yeniden yazildi")
    # KONTROL satirlarini tazele
    t2 = tanitim_oku(md)
    uy = []
    for baslik, body in t2["sec"]:
        for y in TP.YASAK:
            if y in body.lower():
                uy.append(f"- '{y}' ifadesi gecti ({baslik}). Onaylamadan once cikar.")
    yeni = "\n".join(uy) or "- yasakli ifade bulunmadi (yine de elle oku)"
    return re.sub(r"(?ms)^(## KONTROL\n)((?:- [^\n]*\n)+)", lambda m: m.group(1) + yeni + "\n", md, count=1)


# ---------- ORTAK DONGU ----------
def llm_rev(prompt):
    import kado_icerik_hatti as H
    body = {"model": H.MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.2, "num_predict": 700}}
    if H.MODEL.startswith("qwen3"):
        body["think"] = False
    req = urllib.request.Request(H.URL, json.dumps(body).encode("utf-8"), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        t = json.load(r).get("response", "")
    return re.sub(r"<think>.*?</think>", "", t, flags=re.S).strip()


def denetle(d, max_tur=MAX_TUR, gen=None, rev=None, sadece_kontrol=False, hedef=""):
    d = Path(d)
    ic, tn = d / "icerik_paketi.md", d / "tanitim_paketi.md"
    if ic.is_file():
        tip, dosya = "icerik", ic
    elif tn.is_file():
        tip, dosya = "tanitim", tn
    else:
        return None
    if gen is None:
        import kado_icerik_hatti as H
        gen = H.llm
    if rev is None:
        rev = llm_rev
    md = dosya.read_text(encoding=ENC)
    turlar, notlar_tum = [], []
    yaziliyor = tip == "icerik" or bool(hedef)
    for tur in range(max_tur + 1):
        notlar = []
        if tip == "icerik":
            p = icerik_oku(md)
            sor = kontrol_icerik(p)
            if not sadece_kontrol:
                try:
                    sor += parse_review(rev(llm_prompt_icerik(p)), {"METIN": "U14", "GORSEL": "U15g", "HASHTAG": "U15h"}, "U14")
                except Exception as e:
                    notlar.append(f"model denetimi yapilamadi ({type(e).__name__}); sadece kod kontrolu")
        else:
            t = tanitim_oku(md)
            sor = kontrol_tanitim(t, hedef)
            if not sadece_kontrol:
                try:
                    sor += parse_review(rev(llm_prompt_tanitim(t, hedef)), {"MAGAZA": "M", "INFLUENCER": "I", "REKLAM": "R"}, "M")
                except Exception as e:
                    notlar.append(f"model denetimi yapilamadi ({type(e).__name__}); sadece kod kontrolu")
        if not sor or tur == max_tur or sadece_kontrol or not yaziliyor:
            turlar.append((tur, sor, notlar))
            break
        v0 = dosya.with_name(dosya.stem + ".v0" + dosya.suffix)
        if not v0.exists():
            shutil.copy2(dosya, v0)
        if tip == "icerik":
            yeni = birlestir_icerik(md, yaz_icerik(p, sor, gen, notlar))
        else:
            yeni = yaz_tanitim(md, t, hedef, sor, gen, notlar)
        turlar.append((tur, sor, notlar))
        if yeni == md:
            turlar.append((tur + 1, sor, ["yeniden yazim sonuc vermedi, durduruldu"]))
            break
        md = yeni
        dosya.write_text(md, encoding=ENC)
    son_sor = turlar[-1][1]
    yazim = sum(1 for _, _, n in turlar for x in n if "yeniden yazildi" in x)
    karar = "GECTI" if not son_sor else "KALDI"
    r = [f"# Denetci Raporu (U18) - {d.name}", f"Paket: {dosya.name} ({tip})", f"Karar: {karar}",
         f"Yeniden yazim adimi: {yazim}", ""]
    for tur, sor, notlar in turlar:
        r.append(f"## Tur {tur}" + (" (ilk kontrol)" if tur == 0 else ""))
        r += [f"- [{k}] {m}" for k, m in sor] or ["- sorun yok"]
        r += [f"- not: {n}" for n in notlar]
        r.append("")
    if karar == "KALDI":
        r.append("Sorunlar tam cozulmedi: paketi onaylamadan once elle oku.")
    if (dosya.with_name(dosya.stem + ".v0" + dosya.suffix)).exists():
        r.append(f"Orijinal metin: {dosya.stem}.v0{dosya.suffix}")
    r.append("YAYINLANMADI. Karar sende.")
    (d / "denetci_raporu.md").write_text("\n".join(r), encoding=ENC)
    return karar, len(son_sor), yazim, turlar


# ---------- SELFTEST ----------
ORNEK = """# KADO Icerik Paketi: Han Toys
Gorev: X
Hedef: Okul oncesi cocuklar icin egitici oyuncaklar, ebeveynlere sade ve samimi bir dille anlat | HAFIZA: tercih
Platform: instagram
Model: test

## U14 - Gonderi metinleri
1) Han Toys cocuklarin zihinsel gelisimine destek olmak icin ozel tasarlandi. Hemen incele!
2) Han Toys ebeveynler icin egitici oyuncaklar sunuyor, gelin birlikte kesfedin.
3) Han Toys ile cocuklar oynarken ogrenir, ayrintilar icin yazin.

## U15 - Gorsel fikirleri ve hashtag
METIN 1: Han Toys egitici oyuncaklar sunuyor ebeveynler icin gelin birlikte kesfedin.
METIN 2: Bir cocuk halida renkli bloklari diziyor, anne yaninda gulumsuyor.
METIN 3: Masada acik bir kutu ve icinden cikan ahsap yapboz parcalari yakin cekim.
HASHTAG: #HanToys #SadeDil #Egitici #Oyuncak #Cocuk #Ebeveyn #Oyun #Ogren

## U16 - 7 gunluk takvim
Gun 1 | gonderi | tanitim | 08:00
Gun 2 | reel | kutu acilisi | 12:00
Gun 3 | hikaye | soru cevap | 15:00
Gun 4 | gonderi | ebeveyn ipucu | 09:00
Gun 5 | reel | oyun ani | 14:00
Gun 6 | hikaye | kaliteli ve guvenli oyun | 11:00
Gun 7 | gonderi | haftalik ozet | 10:00

## Durum
YAYINLANMADI. Bu taslak insan onayi bekler.
"""


def selftest():
    import kado_icerik_hatti as H
    ok = 0
    tot = [0]

    def _say(c):
        tot[0] += 1
        return 1 if c else 0
    u14 = "\n".join(f"{i}) Han Toys ile cocuklar oynarken ogrenir, {i}. aciklama icin bizi takip edin hemen." for i in range(1, 4))
    gor = "\n".join(f"{i}) Bir cocuk masada {i}. renkli blogu diziyor, yaninda anne sessizce izleyip gulumsuyor." for i in range(1, 4))
    tag = "#HanToys #Egitici #Oyuncak #Cocuk #Ebeveyn #Oyun #Ogren #Yapboz"
    tak = "\n".join(f"Gun {i} | {'reel' if i % 2 else 'gonderi'} | konu numarasi {i} | 10:00" for i in range(1, 8))

    def iyi(p):
        if "metin yazari" in p: return u14
        if "gorsel veya kisa video" in p: return gor
        if "hashtag yaz" in p: return tag
        return tak

    def kotu(p):
        return "1) Han Toys ozel tasarlandi.\n2) Han Toys zihinsel gelisim sunar.\n3) Han Toys kaliteli ve guvenli." if "metin yazari" in p else iyi(p)

    def yeni_dizin():
        d = Path(tempfile.mkdtemp()) / "J1"
        d.mkdir(parents=True)
        (d / "icerik_paketi.md").write_text(ORNEK, encoding=ENC)
        return d
    gecti = lambda p: "KARAR: GECTI"
    # 1) hatali ornek duzelir, biçim korunur, v0 ve rapor var
    d = yeni_dizin()
    k, n, y, _ = denetle(d, 2, iyi, gecti)
    md = (d / "icerik_paketi.md").read_text(encoding=ENC)
    ok += _say(k == "GECTI" and (d / "icerik_paketi.v0.md").exists() and (d / "denetci_raporu.md").exists())
    ok += _say(all(x in md for x in ("## U14 - ", "## U15 - ", "## U16 - ", "METIN 1:", "HASHTAG:", "## Durum")) and "SadeDil" not in md and "zihinsel" not in md)
    # 2) model hep kotu cikarsa KALDI, bicim bozulmaz
    d = yeni_dizin()
    k2, n2, _, _ = denetle(d, 2, lambda p: kotu(p), gecti)
    md2 = (d / "icerik_paketi.md").read_text(encoding=ENC)
    ok += _say(k2 == "KALDI" and "## Durum" in md2 and "METIN 1:" in md2)
    # 3) model denetimi hata verirse kod kontrolu ile devam eder
    d = yeni_dizin()
    def patla(p): raise RuntimeError("ollama yok")
    k3, _, _, tr = denetle(d, 2, iyi, patla)
    ok += _say(k3 == "GECTI" and any("model denetimi yapilamadi" in x for _, _, nn in tr for x in nn))
    # 4) sadece-kontrol dosyayi degistirmez
    d = yeni_dizin()
    k4, n4, _, _ = denetle(d, 2, iyi, gecti, sadece_kontrol=True)
    ok += _say(k4 == "KALDI" and n4 >= 4 and (d / "icerik_paketi.md").read_text(encoding=ENC) == ORNEK)
    # 5) model denetimi KALDI derse bolum yeniden yazilir
    d = yeni_dizin()
    say = {"n": 0}
    def rev(p):
        say["n"] += 1
        return "KARAR: KALDI\nSORUN: [GORSEL] gorsel fikri 1 sahne anlatmiyor" if say["n"] == 1 else "KARAR: GECTI"
    d2 = d
    (d2 / "icerik_paketi.md").write_text(ORNEK.replace("zihinsel gelisimine", "gelisimine").replace("gelisimine destek olmak icin ozel tasarlandi", "oyun deneyimi sunar").replace("kaliteli ve guvenli", "ogrenme").replace("#SadeDil", "#Yapboz"), encoding=ENC)
    k5, _, y5, _ = denetle(d2, 2, iyi, rev)
    ok += _say(k5 == "GECTI" and y5 >= 1)
    # 6) tanitim paketi: uydurma isim, uzunluk, kopya reklam, yer tutucu yakalanir
    t = {"ad": "KADO", "asama": "cikis-oncesi", "sec": [
        ("Magaza", "BASLIK (en fazla 30 karakter)\nBu baslik otuz karakterden cok daha uzun yazilmis\nKISA ACIKLAMA\nKisa"),
        ("Influencer", "### Profil 1: Kamil Karakurt\n- **Isim:** Kamil Karakurt\nMerhaba, haberdar ol."),
        ("Reklam", "**BASLIK:** KADO haberi\n**GOVDE:** Kisa govde [INDIR]\n**BASLIK:** KADO haberi\n**GOVDE:** Kisa govde [INDIR]")]}
    anahtarlar = {k for k, _ in kontrol_tanitim(t, "kisisel asistan")}
    ok += _say({"M", "I", "R"} <= anahtarlar)
    tt = [m for _, m in kontrol_tanitim(t, "kisisel asistan")]
    ok += _say(any("ayni" in m for m in tt) and any("yer tutucu" in m for m in tt) and any("isim" in m for m in tt))
    ok += _say(temizle_yanit("a\n\u2192 Duzeltildi: x\n**Durum:** Uygulama henuz magazada degil\nb") == "a\nb")
    ok += _say(any("karismis" in m for _, m in kontrol_tanitim({"ad": "K", "asama": "yayinda", "sec": [("M", "iyi metin\n- Hedefte olmayan iddia: x")]}, "")))
    print("SELFTEST %d/%d %s" % (ok, tot[0], "BASARILI" if ok == tot[0] else "BASARISIZ"))
    return 0 if ok == tot[0] else 1


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        return selftest()
    ap = argparse.ArgumentParser()
    ap.add_argument("gorev")
    ap.add_argument("--tur", type=int, default=MAX_TUR)
    ap.add_argument("--sadece-kontrol", action="store_true")
    ap.add_argument("--hedef", default="")
    ap.add_argument("--temizle", action="store_true",
                    help="tanitim paketinden modelin metne karistirdigi not/talimat satirlarini siler (yedekli)")
    ap.add_argument("--sil", action="append", default=[], help="paketten bu metni aynen siler (--temizle ile)")
    a = ap.parse_args()
    d = OUT / a.gorev
    if not d.is_dir() and OUT.is_dir():
        c = [x for x in OUT.iterdir() if x.is_dir() and x.name.endswith(a.gorev)]
        d = c[0] if len(c) == 1 else d
    if not d.is_dir():
        print("BULUNAMADI:", a.gorev)
        return 2
    if a.temizle:
        f = d / "tanitim_paketi.md"
        if not f.is_file():
            print("BULUNAMADI: tanitim_paketi.md yok")
            return 2
        md = f.read_text(encoding=ENC)
        v1 = d / "tanitim_paketi.v1.md"
        if not v1.exists():
            shutil.copy2(f, v1)
        bas, _, kon = md.partition("\n## KONTROL")
        silinen = [l for l in bas.splitlines() if sizinti_mi(l)]
        bas = temizle_yanit(bas)
        for x in a.sil:
            if x in bas:
                bas = bas.replace(x, "")
                silinen.append("[metin] " + x)
        f.write_text(bas.rstrip() + ("\n\n## KONTROL" + kon if kon else "\n"), encoding=ENC)
        print(f"TEMIZLENDI: {len(silinen)} satir/parca silindi (yedek: tanitim_paketi.v1.md)")
        for l in silinen:
            print("  silindi:", l.strip()[:110])
        a.sadece_kontrol = True
    r = denetle(d, a.tur, sadece_kontrol=a.sadece_kontrol, hedef=a.hedef)
    if r is None:
        print("BULUNAMADI: icerik_paketi.md / tanitim_paketi.md yok")
        return 2
    karar, kalan, yazim, turlar = r
    for tur, sor, notlar in turlar:
        for k, m in sor:
            print(f"  tur {tur} [{k}] {m}")
    if karar == "GECTI":
        print(f"DENETCI: GECTI ({yazim} yeniden yazim) - YAYINLANMADI, ONAY GEREKLI")
    else:
        print(f"DENETCI: KALDI - {kalan} sorun kaldi, paketi onaylamadan once elle oku (denetci_raporu.md)")
    print("RAPOR:", d / "denetci_raporu.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
