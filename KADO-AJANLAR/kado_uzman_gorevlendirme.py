import ast
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from kado_arastirma_ekibi import github_bilgi
from kado_github_kod_ekibi import github_dosya_oku
from kado_kod_ekibi_v2 import u06_dogrula
from kado_guvenlik_kalite import GuvenlikDenetcisi


def calistir(repo, dosya, ref, rapor_klasoru):
    print("KADO GERCEK UZMAN GOREVLENDIRME TESTI")
    print("=" * 50)

    print("\n[ARASTIRMACI -> U02]")
    bilgi = github_bilgi(repo)
    source = github_dosya_oku(repo, dosya, ref)

    print("DEPO:", bilgi["depo"])
    print("DOSYA:", dosya)
    print("OKUNAN KARAKTER:", len(source))

    print("\n[MIMAR -> U05 + U06]")

    try:
        tree = ast.parse(source)
        print("U05: SOZDIZIMI GECERLI")
    except SyntaxError as exc:
        print("U05: HATA", exc.lineno, exc.msg)
        return 1

    success, message = u06_dogrula(source)
    print("U06:", message)

    if not success:
        return 1

    print("\n[DENETCI -> U07]")

    denetci = GuvenlikDenetcisi()
    denetci.visit(tree)

    print("RISK BULGUSU:", len(denetci.bulgular))

    for satir, aciklama in denetci.bulgular:
        print("SATIR:", satir, "BULGU:", aciklama)

    print("\n[KADO_CEO -> U19]")

    zaman = datetime.now(timezone.utc)
    klasor = Path(rapor_klasoru)
    klasor.mkdir(parents=True, exist_ok=True)

    rapor = {
        "tarih_utc": zaman.isoformat(),
        "gorev": "GitHub Python dosyasi incelemesi",
        "depo": bilgi["depo"],
        "kaynak": bilgi["adres"],
        "dosya": dosya,
        "ref": ref,
        "sonuclar": {
            "U02": {
                "depo_bilgisi": bilgi,
                "okunan_karakter": len(source),
            },
            "U05": "Sozdizimi gecerli",
            "U06": message,
            "U07": {
                "bulgu_sayisi": len(denetci.bulgular),
                "bulgular": denetci.bulgular,
            },
            "U19": "Rapor kaydedildi",
        },
        "sinirlamalar": [
            "Yalnizca Python sozdizimi kontrol edildi",
            "Guvenlik taramasi sinirlidir",
            "Kod calistirilmadi",
            "Ana KADO ajanlari cagrilmadi",
            "Dosyalar degistirilmedi",
        ],
    }

    damga = zaman.strftime("%Y%m%d_%H%M%S_%f")
    ad = bilgi["depo"].replace("/", "_")
    hedef = klasor / f"gorev_{ad}_{damga}.json"

    hedef.write_text(
        json.dumps(rapor, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    kontrol = json.loads(hedef.read_text(encoding="utf-8"))

    if kontrol["depo"] != bilgi["depo"]:
        raise RuntimeError("Rapor dogrulanamadi")

    print("RAPOR:", hedef)
    print("RAPOR DOGRULAMA: BASARILI")

    print("\n[KADO] SONUC")
    print("U02: GERCEK GITHUB VERISI ALDI")
    print("U05: SOZDIZIMINI KONTROL ETTI")
    print("U06: SOZDIZIMINI DOGRULADI")
    print("U07: SINIRLI GUVENLIK TARAMASI YAPTI")
    print("U19: RAPORU KAYDETTI")
    print("ANA KADO SISTEMI DEGISTIRILMEDI")

    return 0


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(
            "Kullanim: python kado_uzman_gorevlendirme.py "
            "sahip/depo dosya.py ref rapor_klasoru"
        )
        sys.exit(2)

    try:
        sys.exit(calistir(*sys.argv[1:]))
    except Exception as exc:
        print("HATA:", type(exc).__name__, str(exc)[:200])
        sys.exit(1)
