import ast
import sys
from pathlib import Path


def kontrol(path):
    path = Path(path).resolve()

    if not path.is_file() or path.suffix.lower() != ".py":
        print("HATA: Gecerli Python dosyasi gerekli")
        return 2

    print("KADO U05 - HATA AVCISI")
    print("DOSYA:", path)

    try:
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(path))

    except SyntaxError as exc:
        print("SOZDIZIMI HATASI BULUNDU")
        print("SATIR:", exc.lineno)
        print("SUTUN:", exc.offset)
        print("ACIKLAMA:", exc.msg)
        print("DURUM: HATALI")
        return 1

    except Exception as exc:
        print("OKUMA HATASI:", type(exc).__name__)
        return 2

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
    print("SOZDIZIMI: GECERLI")
    print("NOT: MANTIK VE GUVENLIK HATALARI TEST EDILMEDI")
    print("DOSYA DEGISTIRILMEDI")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Kullanim: python kado_kod_denetcisi.py dosya.py")
        sys.exit(2)

    sys.exit(kontrol(sys.argv[1]))
