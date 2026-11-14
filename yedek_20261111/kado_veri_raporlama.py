import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from kado_arastirma_ekibi import github_bilgi


def analiz_ve_rapor(repo, rapor_klasoru):
    print("KADO VERI ANALIZI VE RAPORLAMA")
    print("=" * 48)

    print("\n[U17] VERI ANALISTI")

    bilgi = github_bilgi(repo)

    yildiz = bilgi["yildiz"]
    fork = bilgi["fork"]

    if not isinstance(yildiz, int) or not isinstance(fork, int):
        raise ValueError("GitHub metrikleri gecersiz")

    oran = round(fork / yildiz * 100, 2) if yildiz else None

    print("DEPO:", bilgi["depo"])
    print("YILDIZ:", yildiz)
    print("FORK:", fork)
    print("FORK/YILDIZ ORANI:", oran)
    print("DIL:", bilgi["dil"])
    print("LISANS:", bilgi["lisans"])

    print("\n[U19] RAPORLAMA UZMANI")

    zaman = datetime.now(timezone.utc)
    damga = zaman.strftime("%Y%m%d_%H%M%S_%f")

    guvenli_ad = bilgi["depo"].replace("/", "_")
    klasor = Path(rapor_klasoru)
    klasor.mkdir(parents=True, exist_ok=True)

    veri = {
        "rapor_tarihi_utc": zaman.isoformat(),
        "kaynak": "GitHub REST API",
        "depo": bilgi,
        "analiz": {
            "yildiz": yildiz,
            "fork": fork,
            "fork_yildiz_orani_yuzde": oran,
        },
        "sinirlamalar": [
            "Yildiz sayisi kalite garantisi degildir",
            "Fork/yildiz orani kalite puani degildir",
            "Kod guvenligi ve calisma testleri yapilmadi",
        ],
    }

    json_yolu = klasor / f"{guvenli_ad}_{damga}.json"
    md_yolu = klasor / f"{guvenli_ad}_{damga}.md"

    json_yolu.write_text(
        json.dumps(veri, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md = f"""# KADO GitHub Analiz Raporu

**Depo:** {bilgi['depo']}

**Tarih (UTC):** {zaman.isoformat()}

**Kaynak:** {bilgi['adres']}

## U17 Veri Analizi

- Yildiz: {yildiz}
- Fork: {fork}
- Fork/Yildiz Orani: {oran}
- Dil: {bilgi['dil']}
- Lisans: {bilgi['lisans']}
- Arsivlenmis: {bilgi['arsiv']}
- Son push: {bilgi['son_guncelleme']}

## Degerlendirme

Bu rapor GitHub API metriklerine dayanmaktadir.
Yildiz ve fork sayilari yazilim kalitesini veya guvenligini
tek basina kanitlamaz.

## Sinirlamalar

- Kod calistirilmadi.
- Tam guvenlik analizi yapilmadi.
- Depo indirilmedi.
- GitHub deposu degistirilmedi.
"""

    md_yolu.write_text(md, encoding="utf-8")

    print("JSON RAPOR:", json_yolu)
    print("MARKDOWN RAPOR:", md_yolu)

    # Dosyalari yeniden okuyarak temel dogrulama yap.
    kontrol = json.loads(json_yolu.read_text(encoding="utf-8"))

    if kontrol["depo"]["depo"] != bilgi["depo"]:
        raise RuntimeError("Rapor dogrulamasi basarisiz")

    print("\n[KADO] SONUC")
    print("U17: SAYISAL ANALIZ TAMAMLANDI")
    print("U19: IKI RAPOR KAYDEDILDI")
    print("RAPOR OKUMA KONTROLU: BASARILI")
    print("YEREL AI CALISTIRILMADI")
    print("ANA KADO SISTEMI DEGISTIRILMEDI")

    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            "Kullanim: python kado_veri_raporlama.py "
            "sahip/depo rapor_klasoru"
        )
        sys.exit(2)

    try:
        sys.exit(analiz_ve_rapor(sys.argv[1], sys.argv[2]))
    except Exception as exc:
        print("HATA:", type(exc).__name__, str(exc)[:200])
        sys.exit(1)
