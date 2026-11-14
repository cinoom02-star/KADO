import ast
import json
import math
import struct
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2
FRAME_MS = 20

def pcm_test():
    samples = SAMPLE_RATE * FRAME_MS // 1000
    expected_bytes = samples * CHANNELS * SAMPLE_WIDTH

    if samples != 320:
        raise AssertionError("Ornek sayisi yanlis")

    if expected_bytes != 640:
        raise AssertionError("PCM paket boyutu yanlis")

    frequency = 440
    amplitude = 0.25

    values = [
        int(
            amplitude * 32767 *
            math.sin(2 * math.pi * frequency * n / SAMPLE_RATE)
        )
        for n in range(samples)
    ]

    pcm = struct.pack("<" + "h" * len(values), *values)

    if len(pcm) != expected_bytes:
        raise AssertionError("PCM boyutu uyusmuyor")

    restored = struct.unpack(
        "<" + "h" * samples,
        pcm
    )

    if list(restored) != values:
        raise AssertionError("PCM geri okuma hatasi")

    return {
        "sample_rate": SAMPLE_RATE,
        "channels": CHANNELS,
        "sample_width_bytes": SAMPLE_WIDTH,
        "frame_ms": FRAME_MS,
        "samples_per_frame": samples,
        "bytes_per_frame": len(pcm),
        "pcm_roundtrip": True,
    }


def dosya_envanteri():
    targets = [
        ROOT / "kado_canli_gorev.py",
        ROOT / "kado_gorev_calistir.py",
        ROOT / "kado_otomatik_akis.py",
    ]

    results = []

    for path in targets:
        item = {
            "dosya": path.name,
            "mevcut": path.is_file(),
            "python_sozdizimi": None,
        }

        if path.is_file():
            try:
                ast.parse(
                    path.read_text(encoding="utf-8-sig")
                )
                item["python_sozdizimi"] = "gecerli"
            except SyntaxError:
                item["python_sozdizimi"] = "hatali"

        results.append(item)

    return results


def main():
    print("KADO 223 - SES TEKNIK DENETIMI")
    print("=" * 50)

    print("\n[U06] PCM PAKET TESTI")

    pcm = pcm_test()

    for key, value in pcm.items():
        print(key.upper(), ":", value)

    print("\n[U05] KOD YAPISI KONTROLU")

    files = dosya_envanteri()

    for item in files:
        print(
            item["dosya"],
            "| mevcut:", item["mevcut"],
            "| sozdizimi:", item["python_sozdizimi"]
        )

    print("\n[U07] GUVENLIK SINIRLARI")

    print("Canli WhatsApp aramasi: YAPILMADI")
    print("Mikrofon erisimi: YAPILMADI")
    print("Gercek ses dosyasi okunmadi")
    print("API cagrisi: YAPILMADI")
    print("Gecikme olcumu: YAPILMADI")

    report = {
        "asama": 223,
        "tarih_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "gorev_id": 2,
        "yonetici": "MIMAR",
        "uzman_rolleri": ["U05", "U06", "U07"],
        "pcm_test": pcm,
        "dosyalar": files,
        "gercek_whatsapp_ses_akisi_test_edildi": False,
        "gercek_gecikme_olculdu": False,
    }

    report_dir = ROOT / "raporlar"
    report_dir.mkdir(parents=True, exist_ok=True)

    target = report_dir / "kado_223_ses_denetime.json"

    target.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    json.loads(target.read_text(encoding="utf-8"))

    print("\nRAPOR:", target)
    print("223. ASAMA TESTLERI TAMAMLANDI")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(
            "HATA:",
            type(exc).__name__,
            str(exc)[:200]
        )
        sys.exit(1)
