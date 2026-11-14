# KADO - 19 uzman alt ajan kadrosu
# Guvenli, bagimsiz rol kaydi.
# API cagrisi, dosya degisikligi veya gorev calistirma yapmaz.

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class Uzman:
    kod: str
    ad: str
    yonetici: str
    yetenekler: Tuple[str, ...]
    onay_gerekli: bool = True


UZMANLAR = [
    Uzman("U01", "Web Arastirmacisi", "ARASTIRMACI", ("web_arastirma", "kaynak_dogrulama")),
    Uzman("U02", "GitHub Arastirmacisi", "ARASTIRMACI", ("github_arastirma", "depo_analizi")),
    Uzman("U03", "Rakip Analisti", "ARASTIRMACI", ("rakip_analizi", "pazar_arastirmasi")),

    Uzman("U04", "Kod Yazari", "MIMAR", ("kod_uretimi", "refaktor")),
    Uzman("U05", "Hata Avcisi", "MIMAR", ("hata_analizi", "debug")),
    Uzman("U06", "Test Uzmani", "MIMAR", ("test_tasarimi", "test_analizi")),
    Uzman("U08", "Gorsel Uretici", "MIMAR", ("gorsel_uretimi",)),
    Uzman("U09", "Fotograf Duzenleyici", "MIMAR", ("gorsel_duzenleme",)),
    Uzman("U10", "Urun Gorseli Uzmani", "MIMAR", ("urun_gorseli",)),
    Uzman("U11", "Video Uretici", "MIMAR", ("video_uretimi",)),
    Uzman("U12", "Video Kurgucu", "MIMAR", ("video_kurgu",)),

    Uzman("U07", "Guvenlik Denetcisi", "DENETCI", ("guvenlik_inceleme",)),
    Uzman("U13", "Video Analizcisi", "DENETCI", ("video_analizi",)),
    Uzman("U17", "Veri Analisti", "DENETCI", ("veri_analizi",)),
    Uzman("U18", "Kalite Kontrolcu", "DENETCI", ("kalite_kontrol",)),

    Uzman("U14", "Metin Yazari", "KADO_CEO", ("icerik_yazimi",)),
    Uzman("U15", "Sosyal Medya Uzmani", "KADO_CEO", ("sosyal_medya",)),
    Uzman("U16", "Yayin Planlayicisi", "KADO_CEO", ("yayin_planlama",)),
    Uzman("U19", "Raporlama Uzmani", "KADO_CEO", ("raporlama",)),
]


def kadro_kontrol():
    kodlar = [u.kod for u in UZMANLAR]
    assert len(UZMANLAR) == 19, "Uzman sayisi hatali."
    assert len(set(kodlar)) == 19, "Tekrarlanan uzman kodu var."
    assert set(kodlar) == {f"U{i:02d}" for i in range(1, 20)}
    assert all(u.yonetici in {
        "ARASTIRMACI", "MIMAR", "DENETCI", "KADO_CEO"
    } for u in UZMANLAR)
    assert all(u.yetenekler for u in UZMANLAR)
    return True


if __name__ == "__main__":
    kadro_kontrol()

    print("KADO - 19 UZMAN KADROSU")
    print("=" * 48)

    for yonetici in ("ARASTIRMACI", "MIMAR", "DENETCI", "KADO_CEO"):
        uzmanlar = [u for u in UZMANLAR if u.yonetici == yonetici]
        print(f"\n{yonetici} - {len(uzmanlar)} uzman")

        for uzman in uzmanlar:
            print(f"  {uzman.kod}: {uzman.ad}")

    print("\n19/19 UZMAN TANIMI DOGRULANDI")
    print("API CAGIRISI YAPILMADI")
    print("AJAN GOREVI CALISTIRILMADI")
