import json
import re
import sys
import urllib.request


def github_bilgi(repo):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Gecersiz depo adi")

    url = "https://api.github.com/repos/" + repo

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "KADO-Research-Team",
            "Accept": "application/vnd.github+json",
        },
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.load(response)

    return {
        "depo": data.get("full_name"),
        "aciklama": data.get("description"),
        "dil": data.get("language"),
        "yildiz": data.get("stargazers_count"),
        "fork": data.get("forks_count"),
        "lisans": (data.get("license") or {}).get("spdx_id"),
        "arsiv": data.get("archived"),
        "son_guncelleme": data.get("pushed_at"),
        "adres": data.get("html_url"),
    }


def arastir(repo1, repo2):
    print("KADO ARASTIRMA EKIBI")
    print("=" * 48)

    print("\n[U01] VERI TOPLAMA")
    a = github_bilgi(repo1)
    b = github_bilgi(repo2)

    print("IKI DEPONUN GITHUB VERILERI ALINDI")

    print("\n[U02] GITHUB ARASTIRMACISI")

    for item in (a, b):
        print("\nDEPO:", item["depo"])
        print("ACIKLAMA:", item["aciklama"])
        print("DIL:", item["dil"])
        print("LISANS:", item["lisans"])
        print("ARSIV:", item["arsiv"])
        print("SON PUSH:", item["son_guncelleme"])
        print("KAYNAK:", item["adres"])

    print("\n[U03] RAKIP ANALISTI")
    print("GITHUB METRIK KARSILASTIRMASI")

    print(
        f"{a['depo']}: "
        f"{a['yildiz']} yildiz, {a['fork']} fork"
    )

    print(
        f"{b['depo']}: "
        f"{b['yildiz']} yildiz, {b['fork']} fork"
    )

    print("\n[KADO] SONUC")
    print("IKI PROJE ICIN GUNCEL GITHUB METRIKLERI TOPLANDI")
    print("FONKSIYONEL OZELLIKLER KARSILASTIRILMADI")
    print("YILDIZ SAYISI KALITE GARANTISI DEGILDIR")
    print("DEPOLAR INDIRILMEDI")
    print("KOD CALISTIRILMADI")
    print("DOSYALAR DEGISTIRILMEDI")

    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            "Kullanim: python kado_arastirma_ekibi.py "
            "sahip/depo sahip/depo"
        )
        sys.exit(2)

    try:
        sys.exit(arastir(sys.argv[1], sys.argv[2]))
    except Exception as exc:
        print("HATA:", type(exc).__name__, str(exc)[:200])
        sys.exit(1)
