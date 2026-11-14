import ast
import sys
from pathlib import Path


def oner(path):
    path = Path(path).resolve()

    if not path.is_file() or path.suffix.lower() != ".py":
        print("HATA: Python dosyasi gerekli")
        return 2

    source = path.read_text(encoding="utf-8-sig")

    print("KADO U04 - KOD YAZARI")
    print("DOSYA:", path)

    try:
        ast.parse(source, filename=str(path))
        print("SOZDIZIMI: GECERLI")
        print("DUZELTME GEREKMIYOR")
        return 0

    except SyntaxError as exc:
        print("HATA SATIRI:", exc.lineno)
        print("HATA:", exc.msg)

        lines = source.splitlines()

        if not exc.lineno or exc.lineno > len(lines):
            print("OTOMATIK ONERI BULUNAMADI")
            return 0

        line = lines[exc.lineno - 1]
        stripped = line.strip()

        if (
            stripped.startswith(("def ", "if ", "elif ", "else", "for ", "while ", "class "))
            and not stripped.endswith(":")
        ):
            suggestion = line.rstrip() + ":"

            print("\nONERILEN DUZELTME:")
            print("ESKI:", line)
            print("YENI:", suggestion)
            print("NOT: ONERI UYGULANMADAN ONCE TEST EDILMELI")
        else:
            print("BU HATA ICIN GUVENILIR OTOMATIK ONERI YOK")

        print("DOSYA DEGISTIRILMEDI")
        return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Kullanim: python kado_kod_yazari.py dosya.py")
        sys.exit(2)

    sys.exit(oner(sys.argv[1]))
