import sqlite3
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "memory" / "kado_company.db"

KURALLAR = [
    {
        "tur": "kvkk_arastirmasi",
        "kelimeler": ("kvkk", "kisisel veri"),
        "yonetici": "ARASTIRMACI",
        "uzmanlar": ["U01", "U07", "U19"],
    },
    {
        "tur": "sesli_ajan_testi",
        "kelimeler": ("sesli ajan", "sesli asistan"),
        "yonetici": "MIMAR",
        "uzmanlar": ["U05", "U06", "U07"],
    },
    {
        "tur": "oyun_mvp",
        "kelimeler": ("cocuk oyunu", "oyun mvp"),
        "yonetici": "MIMAR",
        "uzmanlar": ["U04", "U06", "U18"],
    },
    {
        "tur": "uygulama_fikirleri",
        "kelimeler": ("uygulama fikir", "uygulama fikri"),
        "yonetici": "ARASTIRMACI",
        "uzmanlar": ["U01", "U03", "U17"],
    },
    {
        "tur": "github_arastirmasi",
        "kelimeler": ("github", "repository"),
        "yonetici": "ARASTIRMACI",
        "uzmanlar": ["U02", "U05", "U07", "U19"],
    },
]


def normalize(metin):
    metin = str(metin or "").casefold()
    metin = metin.translate(
        str.maketrans({
            "ı": "i",
            "ğ": "g",
            "ü": "u",
            "ş": "s",
            "ö": "o",
            "ç": "c",
        })
    )
    return "".join(
        c for c in unicodedata.normalize("NFKD", metin)
        if not unicodedata.combining(c)
    )


def siniflandir(baslik, detay):
    metin = normalize(baslik + " " + detay)

    for kural in KURALLAR:
        if any(
            normalize(kelime) in metin
            for kelime in kural["kelimeler"]
        ):
            return kural

    return None


def gorevleri_oku():
    if not DB.is_file():
        raise FileNotFoundError("KADO veritabani bulunamadi")

    uri = DB.resolve().as_uri() + "?mode=ro"

    with sqlite3.connect(uri, uri=True, timeout=5) as con:
        return con.execute(
            "SELECT id,title,details,status "
            "FROM tasks ORDER BY id"
        ).fetchall()


def main():
    print("KADO 220 - AKILLI GOREV SINIFLANDIRMA")
    print("=" * 50)

    gorevler = gorevleri_oku()
    taninan = 0

    for task_id, title, details, status in gorevler:
        sonuc = siniflandir(title, details)

        print("\nGOREV:", task_id)
        print("BASLIK:", title[:120])
        print("DURUM:", status)

        if sonuc is None:
            print("SINIFLANDIRMA: TANINMADI")
            continue

        taninan += 1

        print("GOREV TURU:", sonuc["tur"])
        print("ANA YONETICI:", sonuc["yonetici"])
        print("UZMANLAR:", ", ".join(sonuc["uzmanlar"]))
        print("DURUM: YONLENDIRME ONERISI HAZIR")

    print("\n[KADO] SONUC")
    print("TOPLAM GOREV:", len(gorevler))
    print("TANINAN GOREV:", taninan)
    print("TANINMAYAN:", len(gorevler) - taninan)
    print("UZMANLAR HENUZ CALISTIRILMADI")
    print("VERITABANI DEGISTIRILMEDI")
    print("ANA KADO VE WHATSAPP DEGISTIRILMEDI")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("HATA:", type(exc).__name__, str(exc)[:150])
        sys.exit(1)
