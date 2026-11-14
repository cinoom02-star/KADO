import ast
import sys
from pathlib import Path

from kado_kod_denetcisi import kontrol


def u04_duzeltme_oner(source, error):
    lines = source.splitlines(keepends=True)

    if not error.lineno or error.lineno > len(lines):
        return None

    index = error.lineno - 1
    original = lines[index]
    stripped = original.strip()

    keywords = (
        "def ", "async def ", "if ", "elif ",
        "for ", "while ", "class ", "with ",
        "try", "except", "else", "finally"
    )

    if not stripped.startswith(keywords):
        return None

    if stripped.endswith(":"):
        return None

    if error.msg != "expected ':'":
        return None

    # Satirin sonundaki newline korunur.
    body = original.rstrip("\r\n")
    ending = original[len(body):]

    lines[index] = body.rstrip() + ":" + ending

    return "".join(lines)


def u06_dogrula(candidate):
    try:
        ast.parse(candidate)
        return True, "SOZDIZIMI GECERLI"
    except SyntaxError as exc:
        return False, (
            f"SATIR {exc.lineno}: {exc.msg}"
        )


def ekip_calistir(path):
    path = Path(path).resolve()

    if not path.is_file() or path.suffix.lower() != ".py":
        print("HATA: Gecerli Python dosyasi gerekli")
        return 2

    print("KADO KOD EKIBI V2")
    print("=" * 45)

    print("\n[U05] HATA AVCISI")
    status = kontrol(path)

    if status == 0:
        print("\nSONUC: SOZDIZIMI GECERLI")
        return 0

    if status != 1:
        return status

    source = path.read_text(encoding="utf-8-sig")

    try:
        ast.parse(source)
    except SyntaxError as exc:
        print("\n[U04] KOD YAZARI")

        candidate = u04_duzeltme_oner(source, exc)

        if candidate is None:
            print("GUVENILIR OTOMATIK DUZELTME YOK")
            return 1

        print("DUZELTME ADAYI OLUSTURULDU")

        print("\n[U06] TEST UZMANI")

        success, message = u06_dogrula(candidate)

        print("TEST:", message)

        if not success:
            print("DUZELTME REDDEDILDI")
            return 1

        original_lines = source.splitlines()
        candidate_lines = candidate.splitlines()

        i = exc.lineno - 1

        print("\nONERILEN DEGISIKLIK:")
        print("ESKI:", original_lines[i])
        print("YENI:", candidate_lines[i])

        print("\n[KADO] SONUC")
        print("U05: HATA TESPIT EDILDI")
        print("U04: DUZELTME ONERILDI")
        print("U06: SOZDIZIMI DOGRULANDI")
        print("CALISMA TESTI YAPILMADI")
        print("DOSYA DEGISTIRILMEDI")

        return 0

    print("BEKLENMEYEN DURUM")
    return 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Kullanim: python kado_kod_ekibi_v2.py dosya.py")
        sys.exit(2)

    sys.exit(ekip_calistir(sys.argv[1]))
