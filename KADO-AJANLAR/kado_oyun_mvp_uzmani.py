import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "memory" / "kado_company.db"

def gorev_oku(task_id):
    if not DB.is_file():
        raise FileNotFoundError("KADO veritabani bulunamadi")

    uri = DB.resolve().as_uri() + "?mode=ro"

    with sqlite3.connect(uri, uri=True, timeout=5) as con:
        return con.execute(
            "SELECT id,title,details,status FROM tasks WHERE id=?",
            (task_id,)
        ).fetchone()

def plan_uret(title, details):
    return {
        "proje": title,
        "kaynak_gorev_aciklamasi": details,
        "plan_turu": "Kural tabanli baslangic MVP taslagi",
        "hedef": "Tek temel mekanige sahip basit bir cocuk oyunu",
        "onerilen_mvp": {
            "ekranlar": [
                "Ana menu",
                "Oyun ekrani",
                "Sonuc ekrani"
            ],
            "temel_ozellikler": [
                "Dokunmatik kontrol",
                "Basit puan sistemi",
                "Yeniden baslatma",
                "Ses acma kapatma"
            ],
            "ilk_surume_alinmayacaklar": [
                "Cok oyunculu mod",
                "Hesap sistemi",
                "Uygulama ici odeme",
                "Kisisel veri toplama"
            ]
        },
        "gelistirme_gorevleri": [
            {"id": "G01", "is": "Oyun mekanigini kesinlestir", "oncelik": 1},
            {"id": "G02", "is": "Ekran akislarini tasarla", "oncelik": 2},
            {"id": "G03", "is": "Dokunmatik kontrolu gelistir", "oncelik": 3},
            {"id": "G04", "is": "Puan sistemini gelistir", "oncelik": 4},
            {"id": "G05", "is": "Ses ve gorselleri ekle", "oncelik": 5},
            {"id": "G06", "is": "Cihaz testlerini tamamla", "oncelik": 6}
        ],
        "test_kriterleri": [
            "Oyun acilisinda hata olmamali",
            "Dokunmatik kontroller calismali",
            "Puan dogru hesaplanmali",
            "Yeniden baslatma calismali",
            "Ses kapatma calismali",
            "Dusuk donanimli cihazda test edilmeli",
            "Cocuklara uygun icerik kontrol edilmeli"
        ],
        "eksik_kararlar": [
            "Oyun turu",
            "Hedef yas araligi",
            "Android veya iOS hedefi",
            "Gorsel stil",
            "Oyun mekanigi"
        ],
        "sinirlamalar": [
            "Bu plan otomatik uretilmis genel bir taslaktir",
            "Gercek oyun kodu uretilmedi",
            "Testler calistirilmadi",
            "Magaza yayin uygunlugu dogrulanmadi"
        ]
    }

def main():
    task_id = 1
    print("KADO 222 - OYUN MVP UZMANI")
    print("=" * 48)

    row = gorev_oku(task_id)

    if not row:
        raise RuntimeError("Gorev bulunamadi")

    _, title, details, status = row

    if "oyun" not in title.casefold():
        raise RuntimeError("Beklenen oyun gorevi degil")

    print("GOREV:", task_id, title)
    print("DURUM:", status)

    plan = plan_uret(title, details)

    zaman = datetime.now(timezone.utc)
    rapor = {
        "gorev_id": task_id,
        "tarih_utc": zaman.isoformat(),
        "yonetici": "MIMAR",
        "uzmanlar": ["U04", "U06", "U18"],
        "plan": plan,
        "gercek_test_yapildi": False,
    }

    klasor = ROOT / "raporlar"
    klasor.mkdir(parents=True, exist_ok=True)

    damga = zaman.strftime("%Y%m%d_%H%M%S_%f")
    hedef = klasor / f"oyun_mvp_{damga}.json"

    hedef.write_text(
        json.dumps(rapor, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    kontrol = json.loads(hedef.read_text(encoding="utf-8"))

    if kontrol["gorev_id"] != task_id:
        raise RuntimeError("Rapor kontrolu basarisiz")

    print("\n[U04] MVP PLANLAMA")
    print("GELISTIRME GOREVI:", len(plan["gelistirme_gorevleri"]))

    print("\n[U06] TEST PLANLAMA")
    print("TEST KRITERI:", len(plan["test_kriterleri"]))

    print("\n[U18] KAPSAM KONTROLU")
    print("EKSIK KARAR:", len(plan["eksik_kararlar"]))

    print("\nRAPOR:", hedef)
    print("RAPOR DOGRULANDI")
    print("OYUN KODU URETILMEDI")
    print("GERCEK TEST CALISTIRILMADI")
    print("ANA KADO VE WHATSAPP DEGISTIRILMEDI")

    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("HATA:", type(exc).__name__, str(exc)[:200])
        sys.exit(1)
