import argparse
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "memory" / "kado_company.db"

REPO_PATTERN = re.compile(
    r"(?<![\w.-])([A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100})(?![\w.-])"
)

GITHUB_WORDS = ("github", "depo", "repository", "repo")


def gorev_oku(task_id):
    if not DB.is_file():
        raise FileNotFoundError("KADO veritabani bulunamadi")

    uri = DB.resolve().as_uri() + "?mode=ro"

    with sqlite3.connect(uri, uri=True, timeout=5) as con:
        row = con.execute(
            "SELECT id, title, details, status "
            "FROM tasks WHERE id=?",
            (task_id,),
        ).fetchone()

    return row


def gorev_cozumle(title, details):
    metin = f"{title}\n{details}"
    lower = metin.lower()

    if not any(word in lower for word in GITHUB_WORDS):
        return None

    match = REPO_PATTERN.search(metin)

    if not match:
        return None

    repo = match.group(1)

    if repo.startswith(".") or ".." in repo:
        return None

    return {
        "tur": "github_depo_inceleme",
        "repo": repo,
        "durum": "uzman_gorevine_uygun",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", type=int, required=True)
    args = parser.parse_args()

    if args.task_id < 1:
        parser.error("Gecerli gorev ID gerekli")

    print("KADO GUVENLI UZMAN KOPRUSU")
    print("=" * 48)

    row = gorev_oku(args.task_id)

    if row is None:
        print("GOREV BULUNAMADI")
        return 2

    task_id, title, details, status = row

    print("GOREV ID:", task_id)
    print("BASLIK:", title[:150])
    print("DURUM:", status)

    sonuc = gorev_cozumle(title, details)

    if sonuc is None:
        print("UZMAN GOREVI: DESTEKLENMIYOR")
        print("HICBIR ISLEM YAPILMADI")
        return 0

    print("UZMAN GOREVI:", sonuc["tur"])
    print("GITHUB DEPOSU:", sonuc["repo"])
    print("GOREV UYGUNLUGU:", sonuc["durum"])

    print("\nTEST MODU")
    print("GITHUB ISTEGI YAPILMADI")
    print("UZMAN ARACLARI CALISTIRILMADI")
    print("VERITABANI DEGISTIRILMEDI")
    print("ANA KADO DEGISTIRILMEDI")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("HATA:", type(exc).__name__, str(exc)[:150])
        sys.exit(1)
