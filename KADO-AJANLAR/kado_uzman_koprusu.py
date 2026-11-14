import importlib
import sys

from kado_19_uzman import UZMANLAR

YONETICILER = {
    "ARASTIRMACI": "arastirmaci",
    "MIMAR": "mimar",
    "DENETCI": "denetci",
    "KADO_CEO": "kado_ceo",
}

ARACLAR = {
    "U01": "kado_arastirma_ekibi",
    "U02": "kado_github_uzmani",
    "U03": "kado_arastirma_ekibi",
    "U04": "kado_kod_yazari",
    "U05": "kado_kod_denetcisi",
    "U06": "kado_kod_ekibi_v2",
    "U07": "kado_guvenlik_kalite",
    "U17": "kado_veri_raporlama",
    "U18": "kado_guvenlik_kalite",
    "U19": "kado_veri_raporlama",
}


def kontrol():
    print("KADO UZMAN ENTEGRASYON KOPRUSU")
    print("=" * 48)

    basarili = 0
    eksik = 0

    for uzman in UZMANLAR:
        kod = uzman.kod
        yonetici = uzman.yonetici
        modul = ARACLAR.get(kod)

        print("\nUZMAN:", kod, uzman.ad)
        print("YONETICI:", yonetici)

        if yonetici not in YONETICILER:
            print("DURUM: GECERSIZ YONETICI")
            eksik += 1
            continue

        if not modul:
            print("DURUM: ARAC HENUZ BAGLANMADI")
            continue

        try:
            importlib.import_module(modul)
            print("ARAC MODULU:", modul)
            print("DURUM: IMPORT BASARILI")
            basarili += 1

        except Exception as exc:
            print("DURUM: IMPORT HATASI")
            print("HATA:", type(exc).__name__, str(exc)[:150])
            eksik += 1

    print("\n[KADO] KOPRU RAPORU")
    print("IMPORT BASARILI:", basarili)
    print("IMPORT HATASI:", eksik)
    print("NOT: IMPORT BASARISI GOREV CALISTIRMA TESTI DEGILDIR")
    print("ANA KADOYA ENTEGRASYON HENUZ YAPILMADI")

    return 0 if eksik == 0 and basarili == 10 else 1


if __name__ == "__main__":
    sys.exit(kontrol())
