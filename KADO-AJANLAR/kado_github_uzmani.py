import json
import re
import sys
import urllib.error
import urllib.request


def github_depo_incele(repo):
    if not re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",
        repo
    ):
        raise ValueError("Gecersiz GitHub depo adi")

    url = f"https://api.github.com/repos/{repo}"

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "KADO-GitHub-Research/1.0"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=20
    ) as response:
        data = json.load(response)

    return {
        "depo": data.get("full_name"),
        "aciklama": data.get("description"),
        "yildiz": data.get("stargazers_count"),
        "fork": data.get("forks_count"),
        "dil": data.get("language"),
        "lisans": (
            (data.get("license") or {}).get("spdx_id")
        ),
        "arsivlenmis": data.get("archived"),
        "son_guncelleme": data.get("pushed_at"),
        "adres": data.get("html_url"),
    }


def main():
    if len(sys.argv) != 2:
        print("Kullanim: python kado_github_uzmani.py sahip/depo")
        return 2

    repo = sys.argv[1]

    try:
        sonuc = github_depo_incele(repo)

    except urllib.error.HTTPError as exc:
        print(f"GITHUB HTTP HATASI: {exc.code}")
        return 1

    except Exception as exc:
        print(f"HATA: {type(exc).__name__}: {exc}")
        return 1

    print("\nKADO U02 - GITHUB ARASTIRMA RAPORU")
    print("=" * 45)

    for alan, deger in sonuc.items():
        print(f"{alan.upper()}: {deger}")

    print("\nDURUM: GERCEK GITHUB VERISI OKUNDU")
    print("KOD INDIRILMEDI VE CALISTIRILMADI")
    print("GITHUB HESABINDA DEGISIKLIK YAPILMADI")

    return 0


if __name__ == "__main__":
    sys.exit(main())
