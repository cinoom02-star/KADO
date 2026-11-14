import json
import re
import sys
import urllib.request

from kado_19_uzman import UZMANLAR, kadro_kontrol
from kado_uzman_yonlendirici import yonlendir

MODEL = "qwen2.5:3b"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

KODLAR = {u.kod: u for u in UZMANLAR}


def cevap_dogrula(cevap):
    bulunan = re.findall(
        r"(?<![A-Za-z0-9])U\d{2}(?![A-Za-z0-9])",
        cevap.upper()
    )

    if len(bulunan) != 1:
        return None

    return KODLAR.get(bulunan[0])


def yerel_ai_sec(gorev):
    roller = "\n".join(
        f"{u.kod}: {u.ad} - {u.yonetici}"
        for u in UZMANLAR
    )

    prompt = f"""Sen KADO'nun gorev dagitim yoneticisisin.

Asagidaki goreve en uygun TEK uzmani sec.

UZMANLAR:
{roller}

GOREV:
{gorev}

Yalnizca uzman kodunu yaz. Ornek: U03
"""

    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 30
        }
    }).encode("utf-8")

    request = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=180) as response:
        data = json.load(response)

    return cevap_dogrula(data.get("response", ""))


def akilli_yonlendir(gorev):
    try:
        uzman = yerel_ai_sec(gorev)

        if uzman is not None:
            return uzman, "YEREL_AI"

    except Exception as exc:
        print(
            "YEREL AI KULLANILAMADI:",
            type(exc).__name__,
            file=sys.stderr
        )

    uzman = yonlendir(gorev)

    if uzman is not None:
        return uzman, "KURALLI_YONLENDIRICI"

    return None, "UZMAN_BULUNAMADI"


def main():
    kadro_kontrol()

    if len(sys.argv) < 2:
        print("Kullanim: python kado_akilli_yonlendirici.py GOREV")
        return 1

    gorev = " ".join(sys.argv[1:]).strip()

    if not gorev:
        print("Bos gorev kabul edilmez.")
        return 1

    uzman, kaynak = akilli_yonlendir(gorev)

    print("\nKADO AKILLI GOREV DAGITIMI")
    print("GOREV:", gorev)
    print("YONTEM:", kaynak)

    if uzman is None:
        print("SONUC: UZMAN SECILEMEDI")
        return 2

    print("UZMAN:", uzman.kod, "-", uzman.ad)
    print("ANA AJAN:", uzman.yonetici)
    print("DURUM: SECILDI - GOREV CALISTIRILMADI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
