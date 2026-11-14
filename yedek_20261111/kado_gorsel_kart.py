"""KADO gorsel kart uretici (U08, sablon tabanli): icerik paketindeki 3 gonderi metninden
1080x1080 (gonderi) ve 1080x1920 (hikaye/reel) PNG kartlar uretir. Ucretsiz, yerel, Pillow gerekir.
Bu bir yapay zeka FOTOGRAF uretici degildir; renkli zemin + yazi kartidir. Hicbir yere yayin yapmaz.
Kullanim: python kado_gorsel_kart.py [son|GOREV_ID] [--renk #1F6FEB] [--font C:\\Windows\\Fonts\\segoeuib.ttf]
         python kado_gorsel_kart.py selftest
"""
import argparse, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "kado_agent_motor" / "ciktilar"
BOYUTLAR = {"kare": (1080, 1080), "hikaye": (1080, 1920)}
FONTLAR = ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "tahomabd.ttf", "DejaVuSans-Bold.ttf"]
FONT_KLASORLERI = ["C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu", "/Library/Fonts"]
EMOJI = re.compile("[\U00010000-\U0010ffff\u2600-\u27bf\ufe0f\u200d]")


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def karisim(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def font_yolu(ozel=None):
    if ozel and pathlib.Path(ozel).exists():
        return ozel
    for k in FONT_KLASORLERI:
        for f in FONTLAR:
            p = pathlib.Path(k) / f
            if p.exists():
                return str(p)
    raise SystemExit("FONT BULUNAMADI. --font ile bir .ttf yolu ver (Turkce karakter destekli).")


def maddeler(metin):
    return [p.strip() for p in re.split(r"(?m)^\s*\d\)\s*", metin) if p.strip()]


def paketi_oku(md):
    t = md.read_text(encoding="utf-8-sig")
    ilk = t.splitlines()[0] if t else ""
    proje = ilk.split(":", 1)[1].strip() if ":" in ilk else "KADO"
    m = re.search(r"(?ms)^## U14[^\n]*\n(.*?)(?=^## |\Z)", t)
    return proje, (maddeler(m.group(1))[:3] if m else [])


def sar(draw, metin, font, maxw):
    satirlar, cur = [], ""
    for w in metin.split():
        deneme = (cur + " " + w).strip()
        if draw.textlength(deneme, font=font) <= maxw:
            cur = deneme
        else:
            if cur:
                satirlar.append(cur)
            cur = w
    if cur:
        satirlar.append(cur)
    return satirlar


def kart_ciz(proje, metin, no, toplam, boyut, renk, fyol):
    from PIL import Image, ImageDraw, ImageFont
    w, h = boyut
    ust = karisim(renk, (0, 0, 0), 0.55)
    img = Image.new("RGB", boyut, renk)
    d = ImageDraw.Draw(img)
    for y in range(h):
        d.line([(0, y), (w, y)], fill=karisim(ust, renk, y / h))
    ac = karisim(renk, (255, 255, 255), 0.55)
    mx = 90
    f_baslik = ImageFont.truetype(fyol, 46)
    d.text((mx, 110), EMOJI.sub("", proje), font=f_baslik, fill=(255, 255, 255))
    d.rectangle([mx, 185, mx + 140, 195], fill=ac)
    govde = EMOJI.sub("", metin).strip()
    ust_y, alt_y = 300, h - 220
    secim = None
    for boy in range(86, 35, -4):
        f = ImageFont.truetype(fyol, boy)
        sat = sar(d, govde, f, w - 2 * mx)
        lh = int(boy * 1.3)
        secim = (f, sat, lh)
        if len(sat) * lh <= alt_y - ust_y:
            break
    f, sat, lh = secim
    y = ust_y + max(0, ((alt_y - ust_y) - len(sat) * lh) // 2)
    for s in sat:
        d.text((mx, y), s, font=f, fill=(255, 255, 255))
        y += lh
    f_alt = ImageFont.truetype(fyol, 36)
    d.text((mx, h - 120), f"{no} / {toplam}", font=f_alt, fill=ac)
    return img


def uret(md, renk=(31, 111, 235), font=None):
    proje, metinler = paketi_oku(md)
    if not metinler:
        raise SystemExit("U14 gonderi metinleri bulunamadi: " + str(md))
    fyol = font_yolu(font)
    hedef = md.parent / "gorseller"
    hedef.mkdir(exist_ok=True)
    dosyalar = []
    for i, m in enumerate(metinler, 1):
        for ad, boyut in BOYUTLAR.items():
            f = hedef / f"kart_{i}_{ad}.png"
            kart_ciz(proje, m, i, len(metinler), boyut, renk, fyol).save(f)
            dosyalar.append(str(f))
    (hedef / "gorsel_raporu.json").write_text(json.dumps(
        {"proje": proje, "dosyalar": dosyalar, "not": "Sablon kartlar, YAYINLANMADI, onay gerekli"},
        ensure_ascii=False, indent=1), encoding="utf-8")
    return dosyalar


def selftest():
    import tempfile
    from PIL import Image
    with tempfile.TemporaryDirectory() as t:
        t = pathlib.Path(t) / "g1"; t.mkdir()
        md = t / "icerik_paketi.md"
        md.write_text("# KADO Icerik Paketi: Han Toys 🚀\nGorev: x\n\n## U14 - Gonderi metinleri\n"
                      "1) Çocuklar için eğitici oyuncaklar: şimdi keşfet, ğüşiçö! 🚀\n"
                      "2) Ebeveynler için sade ve samimi bir anlatım, " + "uzun cümle " * 12 + "\n"
                      "3) Üçüncü gönderi metni burada yer alır.\n\n## U15 - x\nbaska\n", encoding="utf-8-sig")
        d = uret(md)
        assert len(d) == 6
        for f in d:
            im = Image.open(f)
            assert im.size in ((1080, 1080), (1080, 1920))
            ex = im.getextrema()
            assert all(lo != hi for lo, hi in ex)
            beyaz = sum(1 for p in im.crop((90, 300, 400, 700)).getdata() if p == (255, 255, 255))
            assert beyaz > 50, "yazi cizilmemis"
        assert json.loads((md.parent / "gorseller" / "gorsel_raporu.json").read_text(encoding="utf-8"))["proje"].startswith("Han Toys")
    print("SELFTEST 4/4 BASARILI: ayristirma, 6 kart, boyutlar, yazi cizimi (Turkce + emoji temizleme)")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        return selftest()
    try:
        import PIL  # noqa
    except ImportError:
        print("PILLOW YOK. Kur: C:\\KADO\\KADO-AJANLAR\\.venv\\Scripts\\python.exe -m pip install pillow"); return 3
    ap = argparse.ArgumentParser()
    ap.add_argument("gorev", nargs="?", default="son"); ap.add_argument("--renk", default="#1F6FEB"); ap.add_argument("--font")
    a = ap.parse_args()
    if a.gorev == "son":
        adaylar = sorted(OUT.glob("*/icerik_paketi.md"), key=lambda p: p.stat().st_mtime)
        if not adaylar:
            print("icerik_paketi.md bulunamadi"); return 1
        md = adaylar[-1]
    else:
        md = OUT / a.gorev / "icerik_paketi.md"
        if not md.exists():
            print("BULUNAMADI:", md); return 1
    dosyalar = uret(md, hex_rgb(a.renk), a.font)
    print("PAKET:", md.parent.name)
    print("URETILEN KART:", len(dosyalar))
    print("KLASOR:", md.parent / "gorseller")
    print("DURUM: HAZIR - YAYINLANMADI, ONAY GEREKLI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
