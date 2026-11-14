import ast
import sys
import urllib.request
from urllib.parse import quote

from kado_kod_ekibi_v2 import u04_duzeltme_oner, u06_dogrula


def github_dosya_oku(repo, dosya, ref):
    url = (
        "https://raw.githubusercontent.com/"
        + quote(repo, safe="/")
        + "/"
        + quote(ref, safe="")
        + "/"
        + quote(dosya, safe="/")
    )

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "KADO-GitHub-Researcher"}
    )

    with urllib.request.urlopen(req, timeout=15) as response:
        data = response.read(200001)

    if len(data) > 200000:
        raise ValueError("Dosya boyutu siniri asildi")

    return data.decode("utf-8-sig")


def analiz(repo, dosya, ref):
    print("KADO GITHUB + KOD EKIBI")
    print("=" * 45)

    print("\n[U02] GITHUB ARASTIRMACISI")
    print("DEPO:", repo)
    print("DOSYA:", dosya)
    print("REF:", ref)

    source = github_dosya_oku(repo, dosya, ref)

    print("DOSYA OKUNDU:", len(source), "karakter")

    print("\n[U05] HATA AVCISI")

    try:
        ast.parse(source)
        print("SOZDIZIMI: GECERLI")

        print("\n[U06] TEST UZMANI")
        success, message = u06_dogrula(source)
        print("TEST:", message)

        print("\n[KADO] RAPOR")
        print("U02: GITHUB DOSYASINI OKUDU")
        print("U05: SOZDIZIMINI KONTROL ETTI")
        print("U06: SOZDIZIMINI DOGRULADI")
        print("KOD CALISTIRILMADI")
        print("DOSYA DEGISTIRILMEDI")

        return 0 if success else 1

    except SyntaxError as exc:
        print("HATA:", exc.msg)
        print("SATIR:", exc.lineno)

        print("\n[U04] KOD YAZARI")

        candidate = u04_duzeltme_oner(source, exc)

        if candidate is None:
            print("GUVENILIR DUZELTME ONERISI YOK")
            return 1

        print("DUZELTME ADAYI HAZIRLANDI")

        print("\n[U06] TEST UZMANI")
        success, message = u06_dogrula(candidate)
        print("TEST:", message)

        print("\n[KADO] RAPOR")
        print("ONERI DOGRULANDI:", success)
        print("DOSYA DEGISTIRILMEDI")

        return 0 if success else 1


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Kullanim: python kado_github_kod_ekibi.py sahip/depo dosya.py ref")
        sys.exit(2)

    try:
        sys.exit(analiz(sys.argv[1], sys.argv[2], sys.argv[3]))
    except Exception as exc:
        print("HATA:", type(exc).__name__, str(exc)[:200])
        sys.exit(1)
