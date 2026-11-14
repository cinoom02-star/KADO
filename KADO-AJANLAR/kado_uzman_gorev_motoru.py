import re
import sys

from kado_akilli_yonlendirici import akilli_yonlendir
from kado_github_uzmani import github_depo_incele


def gorev_calistir(gorev):
    print("KADO - UZMAN GOREV MOTORU")
    print("=" * 45)
    print("GOREV:", gorev)

    uzman, yontem = akilli_yonlendir(gorev)

    if uzman is None:
        print("SONUC: UZMAN SECILEMEDI")
        return 2

    print("YONTEM:", yontem)
    print("UZMAN:", uzman.kod, "-", uzman.ad)
    print("ANA AJAN:", uzman.yonetici)

    if uzman.kod != "U02":
        print("SONUC: BU UZMANIN ARACI HENUZ BAGLANMADI")
        return 3

    depolar = re.findall(
        r"(?<![\w./-])"
        r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"
        r"(?![\w./-])",
        gorev
    )

    if len(depolar) != 1:
        print("SONUC: TEK BIR GITHUB DEPOSU BELIRTILMELI")
        return 2

    repo = depolar[0]
    print("\nU02 GITHUB ARASTIRMASI BASLIYOR")
    print("DEPO:", repo)

    try:
        sonuc = github_depo_incele(repo)
    except Exception as exc:
        print("GITHUB HATASI:", type(exc).__name__)
        return 1

    print("\nGERCEK GITHUB RAPORU")

    for alan, deger in sonuc.items():
        print(f"{alan.upper()}: {deger}")

    print("\nSONUC: ARASTIRMA TAMAMLANDI")
    print("KOD INDIRILMEDI VE CALISTIRILMADI")
    print("GITHUB HESABINDA DEGISIKLIK YAPILMADI")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Kullanim: python kado_uzman_gorev_motoru.py GOREV")
        sys.exit(2)

    sys.exit(gorev_calistir(" ".join(sys.argv[1:])))
