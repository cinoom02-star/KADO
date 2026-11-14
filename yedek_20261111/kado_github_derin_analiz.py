import json
import re
import sys
import urllib.error
import urllib.request

from kado_github_uzmani import github_depo_incele


def readme_oku(repo):
    if not re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",
        repo
    ):
        raise ValueError("Gecersiz depo adi")

    url = f"https://api.github.com/repos/{repo}/readme"

    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github.raw+json",
            "User-Agent": "KADO-GitHub-Research/1.0"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            raw = response.read(200001)
            if len(raw) > 200000:
                raise ValueError("README boyut siniri asildi")
            return raw.decode("utf-8", errors="replace")

    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def main():
    if len(sys.argv) != 2:
        print("Kullanim: python kado_github_derin_analiz.py sahip/depo")
        return 2

    repo = sys.argv[1]

    try:
        bilgi = github_depo_incele(repo)
        readme = readme_oku(repo)

    except Exception as exc:
        print("HATA:", type(exc).__name__, str(exc)[:200])
        return 1

    print("\nKADO U02 - DERIN GITHUB INCELEMESI")
    print("=" * 50)

    print("DEPO:", bilgi["depo"])
    print("LISANS:", bilgi["lisans"])
    print("DIL:", bilgi["dil"])
    print("ARSIVLENMIS:", bilgi["arsivlenmis"])
    print("ADRES:", bilgi["adres"])

    if readme is None:
        print("\nREADME BULUNAMADI")
        return 0

    print("\nREADME OKUNDU")
    print("KARAKTER:", len(readme))

    basliklar = re.findall(
        r"(?m)^#{1,4}\s+(.+)$",
        readme
    )

    print("\nREADME BASLIKLARI:")

    for baslik in basliklar[:25]:
        print("-", baslik[:120])

    print("\nREADME ILK 2000 KARAKTER:")
    print(readme[:2000])

    print("\nSONUC: README VE DEPO BILGILERI OKUNDU")
    print("KOD CALISTIRILMADI")
    print("DEPO KLONLANMADI")
    print("GITHUB HESABI DEGISTIRILMEDI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
