import sys
from pathlib import Path

from kado_kod_denetcisi import kontrol
from kado_kod_yazari import oner


def ekip_calistir(path):
    path = Path(path).resolve()

    print("KADO KOD EKIBI")
    print("=" * 40)

    print("\n[1] U05 HATA AVCISI")
    sonuc = kontrol(path)

    if sonuc == 0:
        print("\nSONUC: SOZDIZIMI GECERLI")
        print("U04 DUZELTMEYE GEREK DUYMADI")
        return 0

    if sonuc != 1:
        print("\nKONTROL BASARISIZ")
        return sonuc

    print("\n[2] U04 KOD YAZARI")
    oner(path)

    print("\n[3] KADO DENETIM")
    print("DUZELTME ONERISI SUNULDU")
    print("DOSYA DEGISTIRILMEDI")
    print("KULLANICI ONAYI GEREKLI")

    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Kullanim: python kado_kod_ekibi.py dosya.py")
        sys.exit(2)

    sys.exit(ekip_calistir(sys.argv[1]))
