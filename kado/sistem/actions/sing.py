"""
KADO — Sarki soyleme (enstrumansiz / a cappella tarzi)

• Sozler ORIJINALDIR: Gemini istenen tarz/konuya gore yeni sarki yazar (mevcut sarki sozleri kullanilmaz).
• Sadece su durumlarda hazir soz verilebilir: kullanicinin KENDI yazdigi sozler ya da telifsiz/anonim halk turkusu.
• Soyleyis: heceler uzatilir, nefes araliklari ve ritim eklenir; ElevenLabs sesi dusuk "stability" + yuksek "style"
  ayariyla ezgili/duygulu okur. (Gercek melodi degil, ritimli-ezgili bir yorumdur.)
"""

from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from app_config import get_app_config_value
from actions import kado_agent as _ka
from actions import computer_agent as _ca

SING_STOP = threading.Event()
RATE = 24000                       # pcm_24000 → 24 kHz, 16-bit mono
BYTES_PER_MS = RATE * 2 // 1000    # 48

COMPOSE_NEW = """Sen yetenekli bir sarkici ve soz yazarisin. Asagidaki istege gore ENSTRUMANSIZ (sadece ses),
sesli olarak soylenecek ORIJINAL bir sarki yaz. Hicbir mevcut sarkinin sozunu/dizesini kullanma, alintilama.

ISTEK: {request}
TARZ / RUH HALI: {style}

Cikti SADECE su JSON:
{{"title": "...", "lines": [{{"text": "...", "pause_ms": 300}}]}}

KURALLAR:
- 14-20 satir; kisa misralar (3-8 kelime); kafiyeli; bir NAKARAT olsun ve 2 kez tekrar etsin.
- "text" SESLENDIRME icindir: uzatilan heceleri harf tekrariyla yaz ("Seeeni seviyooooorum", "yaaaar"),
  nakaratta ve satir sonlarinda hecelerin uzat; arada "la la laa", "oooh", "hmm" gibi ezgi sesleri kullan.
  Nefes icin virgul ve uc nokta kullan. Parantez, tirnak, emoji, aciklama YAZMA.
- "pause_ms": satir sonu bekleme (nakaratta uzun 700-1000, akista 250-500).
- Dil: Turkce (istek baska dil belirtiyorsa o dil)."""

COMPOSE_GIVEN = """Asagidaki sozler kullanicinin KENDI yazdigi ya da telifsiz bir halk turkusudur. Sozleri DEGISTIRMEDEN,
enstrumansiz soylenmeye uygun hale getir: uzatilan heceleri harf tekrariyla goster ("seeeni", "yaaar"), satir sonlarini
uzat, nefes icin virgul/uc nokta ekle, istersen tekrar eden yerlere "la la" gibi ezgi sesi ekle. Kelimeleri degistirme/atlama.

SOZLER:
{lyrics}

TARZ / RUH HALI: {style}

Cikti SADECE su JSON:
{{"title": "...", "lines": [{{"text": "...", "pause_ms": 300}}]}}"""


def _tts_pcm(text: str, model: str, settings: dict) -> bytes:
    import requests
    key = str(get_app_config_value("elevenlabs_api_key", "")).strip()
    vid = str(get_app_config_value("elevenlabs_voice_id", "")).strip()
    last = ""
    for attempt in range(5):
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
            params={"output_format": "pcm_24000"},
            headers={"xi-api-key": key, "Content-Type": "application/json"},
            json={"text": text, "model_id": model, "voice_settings": settings},
            timeout=60,
        )
        if r.status_code == 200:
            data = r.content
            return data[: len(data) // 2 * 2]
        last = f"ElevenLabs {r.status_code}: {r.text[:160]}"
        if r.status_code == 429:                  # cok fazla es zamanli istek → bekle, tekrar dene
            time.sleep(1.2 * (attempt + 1))
            continue
        break
    raise RuntimeError(last)


def compose(request: str, style: str = "", lyrics: str = "") -> dict:
    style = style.strip() or "duygulu, sicak, dogal"
    if lyrics.strip():
        prompt = COMPOSE_GIVEN.format(lyrics=lyrics.strip()[:3000], style=style)
    else:
        prompt = COMPOSE_NEW.format(request=request.strip() or "kullaniciya ozel kisa bir sarki", style=style)
    text, _ = _ka._generate(prompt, json_mode=True)
    data = _ca._extract_json(text)
    lines = []
    for ln in (data.get("lines") or [])[:30]:
        t = re.sub(r"[\"“”()\[\]*_#]", "", str(ln.get("text", ""))).strip()
        if t:
            try:
                p = int(ln.get("pause_ms", 400))
            except (TypeError, ValueError):
                p = 400
            lines.append({"text": t, "pause_ms": max(150, min(p, 1200))})
    if not lines:
        raise RuntimeError("Sarki sozleri olusmadi.")
    return {"title": str(data.get("title", "")).strip(), "lines": lines}


def perform(request: str, style: str = "", lyrics: str = ""):
    """Generator: sarkiyi PCM (24 kHz, 16-bit, mono) parcalari olarak uretir. Ilk parca hizli gelir."""
    SING_STOP.clear()
    song = compose(request, style, lyrics)
    model = str(get_app_config_value("elevenlabs_sing_model", "") or "eleven_multilingual_v2")
    settings = {"stability": 0.3, "similarity_boost": 0.8, "style": 0.7,
                "use_speaker_boost": True, "speed": 0.9}
    # Ucretsiz planda es zamanli istek siniri dusuk → varsayilan 1 isci (sirayla uret, onceki satir calarken sonrakini hazirla)
    try:
        workers = max(1, min(int(get_app_config_value("elevenlabs_concurrency", 1) or 1), 4))
    except Exception:
        workers = 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_tts_pcm, ln["text"], model, settings) for ln in song["lines"]]
        for ln, fut in zip(song["lines"], futures):
            if SING_STOP.is_set():
                break
            pcm = fut.result()
            for i in range(0, len(pcm), 8192):
                if SING_STOP.is_set():
                    break
                yield pcm[i:i + 8192]
            yield b"\x00" * (ln["pause_ms"] * BYTES_PER_MS)      # nefes / ritim boslugu
        for f in futures:
            f.cancel()
