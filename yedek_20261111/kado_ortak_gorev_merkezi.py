import ast
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from kado_arastirma_ekibi import github_bilgi
from kado_github_kod_ekibi import github_dosya_oku
from kado_kod_ekibi_v2 import u04_duzeltme_oner, u06_dogrula
from kado_guvenlik_kalite import GuvenlikDenetcisi


def gorev(repo, dosya, ref, rapor_klasoru):
    print("KADO ORTAK GOREV MERKEZI")
    print("=" * 50)

    print("\n[ARASTIRMACI] U01 + U02")

    bilgi = github_bilgi(repo)
    source = github_dosya_oku(repo, dosya, ref)

    print("DEPO:", bilgi["depo"])
    print("DOSYA:", dosya)
    print("OKUNAN:", len(source), "karakter")

    print("\n[MIMAR] U04 + U05 + U06")

    candidate = source
    duzeltme = False

    try:
        ast.parse(source)
        print("U05: SOZDIZIMI GECERLI")

    except SyntaxError as exc:
        print("U05: HATA", exc.lineno, exc.msg)
        candidate = u04_duzeltme_oner(source, exc)

        if candidate is None:
            print("U04: DUZELTME ONERISI YOK")
            return 1

        duzeltme = True
        print("U04: DUZELTME ONERILDI")

    success, message = u06_dogrula(candidate)
    print("U06:", message)

    if not success:
        return 1

    print("\n[DENETCI] U07 + U18")

    tree = ast.parse(candidate)
    denetci = GuvenlikDenetcisi()
    denetci.visit(tree)

    functions = sum(
        isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        for n in ast.walk(tree)
    )

    classes = sum(
        isinstance(n, ast.ClassDef)
        for n in ast.walk(tree)
    )

    print("RISK BULGUSU:", len(denetci.bulgular))
    print("FONKSIYON:", functions)
    print("SINIF:", classes)

    print("\n[KADO CEO] U17 + U19")

    zaman = datetime.now(timezone.utc)
    yildiz = bilgi["yildiz"]
    fork = bilgi["fork"]

    oran = (
        round(fork / yildiz * 100, 2)
        if isinstance(yildiz, int)
        and isinstance(fork, int)
        and yildiz > 0
        else None
    )

    rapor = {
        "tarih_utc": zaman.isoformat(),
        "kaynak": bilgi["adres"],
        "depo": bilgi,
        "incelenen_dosya": dosya,
        "ref": ref,
        "uzmanlar": {
            "U01_U02": "GitHub bilgileri toplandi",
            "U04": "Oneri olusturuldu" if duzeltme else "Gerekmedi",
            "U05": "Sozdizimi kontrol edildi",
            "U06": "Sozdizimi dogrulandi",
            "U07": {
                "bulgu_sayisi": len(denetci.bulgular),
                "bulgular": denetci.bulgular,
            },
            "U18": {
                "fonksiyon": functions,
                "sinif": classes,
                "satir": len(candidate.splitlines()),
            },
            "U17": {
                "yildiz": yildiz,
                "fork": fork,
                "fork_yildiz_orani": oran,
            },
            "U19": "JSON rapor kaydi",
        },
        "sinirlamalar": [
            "Kod calistirilmadi",
            "Tam guvenlik denetimi yapilmadi",
            "Duzeltmeler dosyaya uygulanmadi",
            "Ana KADO ajanlarina henuz entegre edilmedi",
        ],
    }

    klasor = Path(rapor_klasoru)
    klasor.mkdir(parents=True, exist_ok=True)

    damga = zaman.strftime("%Y%m%d_%H%M%S_%f")
    ad = bilgi["depo"].replace("/", "_")

    hedef = klasor / f"ortak_{ad}_{damga}.json"

    hedef.write_text(
        json.dumps(rapor, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    kontrol = json.loads(hedef.read_text(encoding="utf-8"))

    if kontrol["incelenen_dosya"] != dosya:
        raise RuntimeError("Rapor dogrulamasi basarisiz")

    print("U17: METRIK ANALIZI TAMAMLANDI")
    print("U19: RAPOR KAYDEDILDI")
    print("RAPOR:", hedef)

    print("\n[KADO] SONUC")
    print("DORT YONETIM GRUBUNUN GOREV AKISI TEST EDILDI")
    print("ANA KADO SISTEMINE ENTEGRASYON YAPILMADI")
    print("KOD CALISTIRILMADI")
    print("PROJE DOSYALARI DEGISTIRILMEDI")

    return 0


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(
            "Kullanim: python kado_ortak_gorev_merkezi.py "
            "sahip/depo dosya.py ref rapor_klasoru"
        )
        sys.exit(2)

    try:
        sys.exit(gorev(*sys.argv[1:]))
    except Exception as exc:
        print("HATA:", type(exc).__name__, str(exc)[:200])
        sys.exit(1)
