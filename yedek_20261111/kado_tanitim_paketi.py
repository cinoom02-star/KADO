# -*- coding: utf-8 -*-
"""KADO TANITIM PAKETI - uygulama/urun tanitimi icin: magaza metni, influencer mesaj taslaklari, reklam metinleri.
Yerel Ollama kullanir (ucretsiz). Hicbir mesaj GONDERMEZ, reklam VERMEZ, para harcamaz.
Sonuc onay kuyruguna 'review' olarak girer (kado_onay.py ile onayla/reddet).
Kullanim:
  python kado_tanitim_paketi.py "KADO" "kisa aciklama" [--asama cikis-oncesi|yayinda]
  python kado_tanitim_paketi.py selftest
"""
import sys, os, re, json, uuid, datetime, urllib.request, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = ROOT / "kado_agent_motor"
YASAK = ("garantili", "%100", "yüzde yüz", "en iyi", "bir numara", "mucize", "kesinlikle", "risksiz", "kazandırır")
MIN_UZUNLUK = 60


def llm_ollama(prompt, model=None, timeout=900):
    model = model or os.environ.get("KADO_ICERIK_MODEL", "qwen2.5:3b")
    body = {"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0.5}}
    if model.startswith("qwen3"):
        body["think"] = False
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate", json.dumps(body).encode("utf-8"),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        t = json.load(r).get("response", "")
    return re.sub(r"<think>.*?</think>", "", t, flags=re.S).strip()


def bolumler(ad, hedef, asama):
    durum = ("Uygulama henuz magazada DEGIL. Cikis oncesi, merak uyandiran bir dil kullan; 'indir' deme, 'haberdar ol' de."
             if asama == "cikis-oncesi" else "Uygulama yayinda. Net ve sade bir dille indirmeye davet et.")
    ortak = (f"Proje: {ad}\nAciklama: {hedef}\nDurum: {durum}\n"
             "Kurallar: Turkce yaz. Abartili vaat verme (garantili, en iyi, mucize, %100 gibi kelimeler yasak). "
             "Olmayan ozellik, rakam, odul, kullanici sayisi veya yorum uydurma. Bilmedigin seyi yazma.\n\n")
    return [
        ("Magaza sayfasi metni (Google Play / App Store)",
         ortak + "Su basliklarla yaz:\nBASLIK (en fazla 30 karakter)\nKISA ACIKLAMA (en fazla 80 karakter)\n"
         "UZUN ACIKLAMA (3-4 kisa paragraf, en fazla 1200 karakter)\nANAHTAR KELIMELER (8 adet, virgulle)"),
        ("Influencer: aday profil tipleri ve mesaj taslaklari",
         ortak + "Once 3 uygun influencer PROFIL TIPI yaz (gercek isim verme, takipci araligi ve konu tipi ver; "
         "kucuk ve orta olcekli hesaplardan basla). Sonra bu kisilere gonderilecek 3 farkli ILK MESAJ taslagi yaz: "
         "samimi, kisa (en fazla 6 cumle), is birligi teklifinin ne oldugu acik, baski yok. "
         "En sonda 1 TAKIP MESAJI taslagi yaz (cevap gelmezse, 1 cumle)."),
        ("Reklam metinleri ve hedef kitle",
         ortak + "3 farkli REKLAM METNI yaz: her biri BASLIK (en fazla 40 karakter) ve GOVDE (en fazla 125 karakter). "
         "Sonra HEDEF KITLE onerisi yaz (yas araligi, ilgi alanlari, konum tipi). Butce veya para rakami yazma."),
    ]


def uret(ad, hedef, asama="cikis-oncesi", llm=llm_ollama, root=ROOT):
    sonuc, hatalar = [], []
    for baslik, prompt in bolumler(ad, hedef, asama):
        metin = ""
        for _ in range(2):
            try:
                metin = (llm(prompt) or "").strip()
            except Exception as ex:
                metin = ""
                hata = f"{type(ex).__name__}: {ex}"
            if len(metin) >= MIN_UZUNLUK:
                break
        if len(metin) < MIN_UZUNLUK:
            hatalar.append(baslik)
            metin = "(uretilemedi - Ollama calisiyor mu?)"
        sonuc.append((baslik, metin))
    uretilen = len(sonuc) - len(hatalar)
    if uretilen == 0:
        return None, hatalar, []
    uyarilar = []
    for baslik, metin in sonuc:
        for k in YASAK:
            if k in metin.lower():
                uyarilar.append(f"'{k}' ifadesi gecti ({baslik}). Onaylamadan once cikar.")
    jid = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    base = Path(root) / "kado_agent_motor"
    out = base / "ciktilar" / jid
    out.mkdir(parents=True, exist_ok=True)
    md = [f"# Tanitim paketi - {ad}", f"Asama: {asama}", f"Tarih: {datetime.datetime.now():%d.%m.%Y %H:%M}", ""]
    for baslik, metin in sonuc:
        md += [f"## {baslik}", metin, ""]
    md += ["## KONTROL"]
    md += [f"- {u}" for u in uyarilar] or ["- yasakli ifade bulunmadi (yine de elle oku)"]
    if hatalar:
        md += ["- EKSIK bolumler: " + ", ".join(hatalar)]
    md += ["", "Influencer mesajlarini KADO gondermez; sen kendi hesabindan elle gonderirsin.",
           "YAYINLANMADI / GONDERILMEDI. Bu taslak insan onayi bekler."]
    (out / "tanitim_paketi.md").write_text("\n".join(md), encoding="utf-8-sig")
    # kado_onay.py goster komutu OZET.txt'yi de gosterir
    (out / "OZET.txt").write_text("\n".join(md[:60]), encoding="utf-8-sig")
    q = base / "kuyruk"
    q.mkdir(parents=True, exist_ok=True)
    (q / f"{jid}.review").write_text(json.dumps({"id": jid, "kind": "tanitim", "goal": f"{ad}: tanitim paketi ({asama})"},
                                                ensure_ascii=False), encoding="utf-8")
    return jid, hatalar, uyarilar


def selftest():
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        uzun = "Bu bir deneme metnidir ve yeterince uzundur. " * 3
        jid, h, u = uret("Test", "x", llm=lambda p: uzun, root=t)
        assert jid and not h and not u
        assert (t / "kado_agent_motor" / "ciktilar" / jid / "tanitim_paketi.md").exists()
        j = json.loads((t / "kado_agent_motor" / "kuyruk" / f"{jid}.review").read_text(encoding="utf-8"))
        assert j["kind"] == "tanitim" and j["goal"].startswith("Test:")
        # yasakli ifade yakalanir
        jid2, h2, u2 = uret("Test", "x", llm=lambda p: "Bu uygulama garantili sonuc verir ve cok iyidir, hemen dene. " * 2, root=t)
        assert u2 and "garantili" in u2[0]
        assert "garantili" in (t / "kado_agent_motor" / "ciktilar" / jid2 / "tanitim_paketi.md").read_text(encoding="utf-8-sig")
        # kisa cikti reddedilir, hicbiri uretilemezse kuyruga girmez
        n0 = len(list((t / "kado_agent_motor" / "kuyruk").glob("*")))
        jid3, h3, _ = uret("Test", "x", llm=lambda p: "kisa", root=t)
        assert jid3 is None and len(h3) == 3 and len(list((t / "kado_agent_motor" / "kuyruk").glob("*"))) == n0
        # Ollama hatasi (istisna) kuyruga girmez
        def bozuk(p): raise RuntimeError("kapali")
        assert uret("Test", "x", llm=bozuk, root=t)[0] is None
        # bir bolum basarisiz olursa digerleri kalir ve EKSIK yazilir
        sira = iter([uzun, "k", "k", uzun, uzun])
        jid4, h4, _ = uret("Test", "x", llm=lambda p: next(sira), root=t)
        assert jid4 and len(h4) == 1
        assert "EKSIK" in (t / "kado_agent_motor" / "ciktilar" / jid4 / "tanitim_paketi.md").read_text(encoding="utf-8-sig")
    print("SELFTEST 5/5 BASARILI: uretim+kuyruk, yasakli ifade, kisa cikti, hata, kismi uretim")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        return selftest()
    ap = argparse.ArgumentParser()
    ap.add_argument("ad"); ap.add_argument("hedef")
    ap.add_argument("--asama", choices=["cikis-oncesi", "yayinda"], default="cikis-oncesi")
    a = ap.parse_args()
    jid, hatalar, uyarilar = uret(a.ad, a.hedef, a.asama)
    if not jid:
        print("HATA: hicbir bolum uretilemedi. Ollama calisiyor mu? (ollama serve)")
        return 1
    print(f"GOREV: {jid}")
    print(f"CIKTI: {BASE / 'ciktilar' / jid / 'tanitim_paketi.md'}")
    for u in uyarilar:
        print("UYARI:", u)
    if hatalar:
        print("EKSIK:", ", ".join(hatalar))
    print("DURUM: TAMAMLANDI - YAYINLANMADI, GONDERILMEDI, ONAY GEREKLI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
