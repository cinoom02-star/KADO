import ast
import sys

from kado_arastirma_ekibi import github_bilgi
from kado_github_kod_ekibi import github_dosya_oku
from kado_kod_ekibi_v2 import u04_duzeltme_oner, u06_dogrula
from kado_guvenlik_kalite import GuvenlikDenetcisi


def calistir(repo, dosya, ref):
    print("KADO BIRLESIK ARASTIRMA VE KOD EKIBI")
    print("=" * 50)

    print("\n[U01 + U02] GITHUB ARASTIRMASI")

    bilgi = github_bilgi(repo)

    print("DEPO:", bilgi["depo"])
    print("DIL:", bilgi["dil"])
    print("LISANS:", bilgi["lisans"])
    print("ARSIV:", bilgi["arsiv"])
    print("KAYNAK:", bilgi["adres"])

    source = github_dosya_oku(repo, dosya, ref)

    print("DOSYA:", dosya)
    print("OKUNAN KARAKTER:", len(source))

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
            print("DUZELTME ONERISI BULUNAMADI")
            return 1

        duzeltme = True
        print("DUZELTME ADAYI OLUSTURULDU")

    print("\n[U06] TEST UZMANI")

    success, message = u06_dogrula(candidate)
    print("SONUC:", message)

    if not success:
        return 1

    tree = ast.parse(candidate)

    print("\n[U07] GUVENLIK DENETCISI")

    denetci = GuvenlikDenetcisi()
    denetci.visit(tree)

    for satir, aciklama in denetci.bulgular:
        print("BULGU:", satir, aciklama)

    if not denetci.bulgular:
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
    print("RISK BULGUSU:", len(denetci.bulgular))

    print("\n[KADO] BIRLESIK RAPOR")

    print("GITHUB ARASTIRMASI: TAMAMLANDI")
    print("KOD SOZDIZIMI: DOGRULANDI")
    print("DUZELTME:", "ONERILDI" if duzeltme else "GEREKMEDI")
    print("GUVENLIK: SINIRLI STATIK TARAMA")
    print("KALITE: YAPISAL KONTROL")
    print("TAM GUVENLIK VE CALISMA TESTI YAPILMADI")
    print("GITHUB DEPOSU DEGISTIRILMEDI")
    print("KOD CALISTIRILMADI")
    print("DOSYA DEGISTIRILMEDI")

    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Kullanim: python kado_birlesik_arastirma.py sahip/depo dosya.py ref")
        sys.exit(2)

    try:
        sys.exit(calistir(sys.argv[1], sys.argv[2], sys.argv[3]))
    except Exception as exc:
        print("HATA:", type(exc).__name__, str(exc)[:200])
        sys.exit(1)
