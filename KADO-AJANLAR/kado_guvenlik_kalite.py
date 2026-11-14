import ast
import sys
from pathlib import Path


class GuvenlikDenetcisi(ast.NodeVisitor):
    def __init__(self):
        self.bulgular = []
        self.importlar = {}

    def visit_Import(self, node):
        for item in node.names:
            self.importlar[item.asname or item.name] = item.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            for item in node.names:
                self.importlar[item.asname or item.name] = (
                    node.module + "." + item.name
                )
        self.generic_visit(node)

    def visit_Call(self, node):
        name = self.call_name(node.func)

        if name in ("eval", "exec"):
            self.bulgular.append(
                (node.lineno, "Dinamik kod calistirma: " + name)
            )

        if name in (
            "os.system",
            "subprocess.run",
            "subprocess.Popen",
            "subprocess.call",
        ):
            self.bulgular.append(
                (node.lineno, "Komut calistirma incelemesi gerekli: " + name)
            )

        if name in ("pickle.loads", "pickle.load"):
            self.bulgular.append(
                (node.lineno, "Guvenilmeyen veri icin pickle riski")
            )

        self.generic_visit(node)

    def call_name(self, func):
        if isinstance(func, ast.Name):
            return self.importlar.get(func.id, func.id)

        if isinstance(func, ast.Attribute):
            base = self.call_name(func.value)
            return base + "." + func.attr if base else func.attr

        return ""


def incele(path):
    path = Path(path).resolve()

    if not path.is_file() or path.suffix.lower() != ".py":
        print("HATA: Gecerli Python dosyasi gerekli")
        return 2

    print("KADO GUVENLIK + KALITE EKIBI")
    print("=" * 45)
    print("DOSYA:", path)

    try:
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        print("SOZDIZIMI HATASI:", exc.msg)
        return 1
    except Exception as exc:
        print("OKUMA HATASI:", type(exc).__name__)
        return 2

    print("\n[U07] GUVENLIK DENETCISI")

    denetci = GuvenlikDenetcisi()
    denetci.visit(tree)

    if denetci.bulgular:
        for satir, aciklama in denetci.bulgular:
            print("INCELEME:", satir, aciklama)
    else:
        print("TANIMLI RISK KALIPLARI BULUNMADI")

    print("\n[U18] KALITE KONTROLCU")

    functions = [
        n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    classes = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.ClassDef)
    ]

    print("SOZDIZIMI: GECERLI")
    print("FONKSIYON:", len(functions))
    print("SINIF:", len(classes))
    print("SATIR:", len(source.splitlines()))
    print("GUVENLIK BULGUSU:", len(denetci.bulgular))

    print("\n[KADO] RAPOR")
    print("U07: SINIRLI STATIK RISK TARAMASI TAMAMLANDI")
    print("U18: YAPISAL KALITE KONTROLU TAMAMLANDI")
    print("TAM GUVENLIK DENETIMI YAPILMADI")
    print("KOD CALISTIRILMADI")
    print("DOSYA DEGISTIRILMEDI")

    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Kullanim: python kado_guvenlik_kalite.py dosya.py")
        sys.exit(2)

    sys.exit(incele(sys.argv[1]))
