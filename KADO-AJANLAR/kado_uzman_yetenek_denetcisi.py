import ast
import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

from kado_gorev_siniflandirici import siniflandir

ROOT = Path(__file__).resolve().parent
DB = ROOT / "memory" / "kado_company.db"

ARACLAR = {
    "U01": ("kado_arastirma_ekibi.py", ["github_bilgi"]),
    "U02": ("kado_github_kod_ekibi.py", ["github_dosya_oku"]),
    "U03": ("kado_arastirma_ekibi.py", ["github_bilgi"]),
    "U04": ("kado_kod_ekibi_v2.py", ["u04_duzeltme_oner"]),
    "U05": ("kado_kod_denetcisi.py", []),
    "U06": ("kado_kod_ekibi_v2.py", ["u06_dogrula"]),
    "U07": ("kado_guvenlik_kalite.py", ["GuvenlikDenetcisi"]),
    "U17": ("kado_veri_raporlama.py", ["analiz_ve_rapor"]),
    "U18": ("kado_guvenlik_kalite.py", ["GuvenlikDenetcisi"]),
    "U19": ("kado_veri_raporlama.py", ["analiz_ve_rapor"]),
}

GEREKSINIMLER = {
    "oyun_mvp": [
        "Oyun gereksinimlerini belirleme",
        "Oynanabilir prototip uretme",
        "Uygulama testleri",
    ],
    "sesli_ajan_testi": [
        "Ses giris cikis testi",
        "Gecikme olcumu",
        "WhatsApp ses koprusu dogrulamasi",
    ],
    "uygulama_fikirleri": [
        "Canli pazar arastirmasi",
        "Rakip analizi",
        "Talep ve gelir potansiyeli degerlendirmesi",
    ],
    "kvkk_arastirmasi": [
        "Resmi mevzuat kaynagi okuma",
        "Kaynak ve tarih dogrulama",
        "Hukuki belirsizlikleri raporlama",
    ],
}

def fonksiyonlari_oku(dosya):
    path = ROOT / dosya

    if not path.is_file():
        return None

    tree = ast.parse(path.read_text(encoding="utf-8-sig"))

    return {
        node.name
        for node in tree.body
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        )
    }


def gorevleri_oku():
    uri = DB.resolve().as_uri() + "?mode=ro"

    with sqlite3.connect(uri, uri=True, timeout=5) as con:
        return con.execute(
            "SELECT id,title,details,status FROM tasks ORDER BY id"
        ).fetchall()


def main():
    print("KADO 221 - UZMAN YETENEK DENETIMI")
    print("=" * 50)

    if not DB.is_file():
        raise FileNotFoundError("Gorev veritabani bulunamadi")

    rapor = {
        "tarih_utc": datetime.now(timezone.utc).isoformat(),
        "gorevler": [],
        "not": (
            "Fonksiyon varligi gercek gorev yeterliligini "
            "veya basarili calismayi kanitlamaz."
        ),
    }

    for task_id, title, details, status in gorevleri_oku():
        kural = siniflandir(title, details)

        print("\nGOREV:", task_id, "-", title)

        if kural is None:
            print("SINIFLANDIRILAMADI")
            continue

        print("YONETICI:", kural["yonetici"])

        uzman_sonuclari = []

        for kod in kural["uzmanlar"]:
            arac = ARACLAR.get(kod)

            if not arac:
                print(kod, "ARAC TANIMI YOK")
                uzman_sonuclari.append({
                    "uzman": kod,
                    "durum": "arac_tanimi_yok",
                })
                continue

            dosya, beklenenler = arac
            mevcut = fonksiyonlari_oku(dosya)

            if mevcut is None:
                durum = "dosya_eksik"
                bulunan = []
            else:
                bulunan = sorted(
                    set(beklenenler) & mevcut
                )
                durum = (
                    "fonksiyon_mevcut"
                    if len(bulunan) == len(beklenenler)
                    else "fonksiyon_eksik"
                )

                if not beklenenler:
                    durum = "fonksiyon_eslesmesi_tanimlanmamis"

            print(
                kod,
                "DOSYA:", dosya,
                "DURUM:", durum,
                "BULUNAN:", ", ".join(bulunan) or "-"
            )

            uzman_sonuclari.append({
                "uzman": kod,
                "dosya": dosya,
                "durum": durum,
                "fonksiyonlar": bulunan,
            })

        gereksinimler = GEREKSINIMLER.get(
            kural["tur"], []
        )

        print("GOREV ICIN GEREKEN YETENEKLER:")

        for madde in gereksinimler:
            print(" -", madde)

        print("NOT: BU YETENEKLER HENUZ UCTAN UCA DOGRULANMADI")

        rapor["gorevler"].append({
            "id": task_id,
            "baslik": title,
            "tur": kural["tur"],
            "yonetici": kural["yonetici"],
            "uzmanlar": uzman_sonuclari,
            "gereken_yetenekler": gereksinimler,
            "uctan_uca_dogrulandi": False,
        })

    hedef = ROOT / "raporlar" / "kado_221_yetenek_denetcisi.json"
    hedef.parent.mkdir(parents=True, exist_ok=True)

    hedef.write_text(
        json.dumps(rapor, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    json.loads(hedef.read_text(encoding="utf-8"))

    print("\nRAPOR:", hedef)
    print("VERITABANI SALT OKUNUR")
    print("UZMAN FONKSIYONLARI CALISTIRILMADI")
    print("ANA KADO VE WHATSAPP DEGISTIRILMEDI")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("HATA:", type(exc).__name__, str(exc)[:200])
        sys.exit(1)
