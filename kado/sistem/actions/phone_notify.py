"""
KADO → telefonuna WhatsApp mesaji (ucretsiz CallMeBot servisi ile, KENDINE mesaj).

Kurulum (bir kere, ~2 dk):
  1) callmebot.com/blog/free-api-whatsapp-messages/ sayfasindaki adimlari izle
     (WhatsApp'tan bota "I allow callmebot to send me messages" yazarsin, sana APIKEY gelir).
  2) sistem/config/api_keys.json icine yaz:
        "callmebot_phone":  "+905xxxxxxxxx",
        "callmebot_apikey": "123456"
Not: Mesajlar CallMeBot (3. parti) uzerinden gecer; cok gizli seyler yazdirma.
Tek yonludur: sen cevap yazarsan Kado okumaz (konusmak icin Kado'yu sesle/Telefon panelinden kullan).
"""

from __future__ import annotations

import ctypes
import threading
import time

from app_config import get_app_config_value


def configured() -> bool:
    return bool(str(get_app_config_value("callmebot_phone", "") or "").strip()
                and str(get_app_config_value("callmebot_apikey", "") or "").strip())


def idle_seconds() -> float:
    """Kullanici bilgisayarda en son ne zaman fare/klavye kullandi (sn). Windows disinda 0."""
    try:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return max(0.0, (ctypes.windll.kernel32.GetTickCount() - info.dwTime) / 1000.0)
    except Exception:
        pass
    return 0.0


_last_send = 0.0
_lock = threading.Lock()


def send_whatsapp_self(text: str) -> str:
    global _last_send
    text = (text or "").strip()
    if not text:
        return "Mesaj bos."
    if not configured():
        return ("WhatsApp mesaj ayari yok. sistem/config/api_keys.json icine callmebot_phone ve "
                "callmebot_apikey yazilmali (adimlar: ELEVENLABS_KURULUM.txt yaninda TELEFON_MESAJ_KURULUM.txt).")
    import requests
    phone = str(get_app_config_value("callmebot_phone", "")).strip()
    key = str(get_app_config_value("callmebot_apikey", "")).strip()
    with _lock:                       # servis hizli ardisik mesajlari reddedebilir
        wait = 3.0 - (time.time() - _last_send)
        if wait > 0:
            time.sleep(wait)
        try:
            r = requests.get("https://api.callmebot.com/whatsapp.php",
                             params={"phone": phone, "text": text[:900], "apikey": key}, timeout=25)
        except Exception as e:  # noqa: BLE001
            return f"Mesaj gonderilemedi: {str(e)[:120]}"
        finally:
            _last_send = time.time()
    if r.status_code == 200:
        return "WhatsApp'tan telefonuna yazdim."
    return f"Mesaj gonderilemedi (HTTP {r.status_code}): {r.text[:120]}"


def maybe_forward(text: str):
    """Kullanici bilgisayar basinda degilse (AFK) bildirimi telefona da yolla. Arka planda calisir."""
    if not configured():
        return
    try:
        away = float(get_app_config_value("away_minutes", 3) or 3) * 60
    except Exception:
        away = 180
    if idle_seconds() < away:
        return
    threading.Thread(target=lambda: send_whatsapp_self("KADO: " + text), daemon=True).start()
