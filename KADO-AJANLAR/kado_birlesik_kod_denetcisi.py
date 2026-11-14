import ast
import sys
from pathlib import Path

from kado_kod_ekibi_v2 import u04_duzeltme_oner, u06_dogrula
from kado_guvenlik_kalite import GuvenlikDenetcisi


def denetle(path):
    path = Path(path).resolve()

    if not path.is_file() or path.suffix.lower() != ".py":
        print("HATA: Gecerli Python dosyasi gerekli")
        return 2

    source = path.read_text(encoding="utf-8-sig")

    print("KADO BIRLESIK KOD DENETIM MERKEZI")
    print("=" * 48)
    print("DOSYA:", path)

    print("\n[U05] HATA AVCISI")

    candidate = source
    duzeltme = False

    try:
        ast.parse(source)
        print("SOZDIZIMI GECERLI")

    except SyntaxError as exc:
        print("HATA:", exc.msg)
        print("SATIR:", exc.lineno)

        print("\n[U04] KOD YAZARI")

        candidate = u04_duzeltme_oner(source, exc)

        if candidate is None:
            print("DUZELTME ONERISI YOK")
            return 1

        duzeltme = True
        print("DUZELTME ADAYI OLUSTURULDU")

    print("\n[U06] TEST UZMANI")

    success, message = u06_dogrula(candidate)
    print("SONUC:", message)

    if not success:
        return 1

    if duzeltme:
        print("NOT: DUZELTME YALNIZCA BELLEKTE DOGRULANDI")

    print("\n[U07] GUVENLIK DENETCISI")

    tree = ast.parse(candidate)
    denetci = GuvenlikDenetcisi()
    denetci.visit(tree)

    if denetci.bulgular:
        for satir, aciklama in denetci.bulgular:
            print("BULGU:", satir, aciklama)
    else:
        print("TANIMLI RISK KALIPLARI BULUNMADI")

    print("\n[U18] KALITE KONTROLCU")

    functions = sum(
        isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        for n in ast.walk(tree)
    )

    classes = sum(
        isinstance(n, ast.ClassDef)
        for n in ast.walk(tree)
    )

    print("FONKSIYON:", functions)
    print("SINIF:", classes)
    print("SATIR:", len(candidate.splitlines()))
    print("GUVENLIK BULGUSU:", len(denetci.bulgular))

    print("\n[KADO] NIHAI RAPOR")
    print("U05: TAMAMLANDI")
    print("U04:", "ONERI OLUSTURDU" if duzeltme else "DUZELTME GEREKMEDI")
    print("U06: SOZDIZIMI DOGRULANDI")
    print("U07: SINIRLI RISK TARAMASI TAMAMLANDI")
    print("U18: YAPISAL KONTROL TAMAMLANDI")
    print("GUVENLIK GARANTISI VERILMEZ")
    print("KOD CALISTIRILMADI")
    print("DOSYA DEGISTIRILMEDI")

    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Kullanim: python kado_birlesik_kod_denetcisi.py dosya.py")
        sys.exit(2)

    try:
        sys.exit(denetle(sys.argv[1]))
    except Exception as exc:
        print("HATA:", type(exc).__name__, str(exc)[:200])
        sys.exit(2)
