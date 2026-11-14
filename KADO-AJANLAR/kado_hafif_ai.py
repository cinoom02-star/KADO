import json
import time
import urllib.request

URL = "http://127.0.0.1:11434/api/generate"

def hafif_ai(prompt):
    payload = {
        "model": "qwen2.5:3b",
        "prompt": prompt[:2500],
        "stream": False,
        "keep_alive": 0,
        "options": {
            "num_thread": 2,
            "num_ctx": 2048,
            "num_predict": 250,
            "temperature": 0.1
        }
    }

    request = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.load(response)

    return result.get("response", "").strip()


if __name__ == "__main__":
    print("KADO HAFIF AI TESTI")
    print("MODEL: qwen2.5:3b")
    print("CPU THREAD: 2")
    print("CONTEXT: 2048")

    start = time.monotonic()

    answer = hafif_ai(
        "Turkce tek cumleyle cevap ver: "
        "KADO GitHub arastirmacisinin gorevi nedir?"
    )

    print("\nCEVAP:", answer)
    print("SURE:", round(time.monotonic() - start, 1), "saniye")
    print("TEST TAMAMLANDI")
