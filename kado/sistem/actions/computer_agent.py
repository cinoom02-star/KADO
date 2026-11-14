"""
KADO — Bilgisayar kontrolü (Windows)

Kado ekrana bakar (Gemini vision), sonra fare ve klavye ile görevi adım adım yapar.
Arka planda çalışır; Kado konuşmaya devam edebilir.

GUVENLIK:
  • Geri alinamaz her adimda (satin alma, odeme, mesaj/e-posta gonderme, silme,
    form onaylama...) KULLANICIYA SORAR ve cevap gelmeden devam etmez.
  • Sifre, kart bilgisi, SMS/dogrulama kodu ASLA yazmaz; gerekirse kullaniciya sorar.
  • ACIL DURDURMA: farenin imlecini ekranin SOL UST KOSESINE gotur,
    ya da ESC tusuna ~1 saniye basili tut. ("Kado dur" demek de calisir.)
  • En fazla MAX_STEPS adim atar.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import io
import json
import re
import threading
import time
import webbrowser

from app_config import get_app_config_value

MAX_STEPS = 25
# Adim sonrasi bekleme (sn): sayfa degisecekse uzun, sadece yazma/tiklama ise kisa
DELAYS = {"open_url": 2.6, "click": 0.9, "double_click": 1.0, "right_click": 0.7,
          "type": 0.25, "key": 1.2, "hotkey": 0.8, "scroll": 0.5, "wait": 1.8}
CHAIN_DELAY = 0.35        # ayni zincirdeki adimlar arasi
MAX_CHAIN = 4             # tek model cevabinda en fazla kac adim
CONFIRM_TIMEOUT = 150     # kullanici cevabi icin bekleme (sn)
SHOT_MAX_W = 1100

# Gemini 2.0 / 2.5 flash kapatildi; guncel modeller. Hepsi 404 verirse otomatik kesfeder.
VISION_MODELS = (
    "models/gemini-3.6-flash",
    "models/gemini-3.5-flash-lite",
    "models/gemini-3.1-flash-lite",
)
_WORKING_MODEL: str | None = None
_THINK_OK = True    # "dusunmeyi kis" ayari desteklenmiyorsa otomatik kapanir


def _is_not_found(e: Exception) -> bool:
    m = str(e).lower()
    return "404" in m or "not_found" in m or "no longer available" in m or "not found" in m


def _discover_models(client) -> list[str]:
    """API'nin gercekte sundugu flash modellerini bulur (yeniden adlandirmalara dayanikli)."""
    found = []
    try:
        for m in client.models.list():
            name = getattr(m, "name", "") or ""
            low = name.lower()
            acts = [str(a).lower() for a in (getattr(m, "supported_actions", None) or [])]
            if "flash" not in low or any(x in low for x in ("image", "tts", "live", "audio", "embed", "robot", "transcribe", "omni")):
                continue
            if acts and "generatecontent" not in acts:
                continue
            ver = re.search(r"gemini-(\d+)(?:\.(\d+))?", low)
            key = (int(ver.group(1)), int(ver.group(2) or 0)) if ver else (0, 0)
            found.append((key, "lite" in low, name))
    except Exception:
        return []
    found.sort(key=lambda t: (t[0], not t[1]), reverse=True)
    return [n for _, _, n in found[:4]]

BLOCKED_HOTKEYS = {
    "alt+f4", "ctrl+alt+delete", "ctrl+shift+esc", "win+r", "win+x",
    "win+l", "ctrl+alt+del",
}

user32 = ctypes.windll.user32

# ── Win32 girdi ──────────────────────────────────────────────────────────────
_PUL = ctypes.POINTER(ctypes.c_ulong)


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", _PUL)]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", _PUL)]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("ii", _INPUT_UNION)]


_VK = {
    "enter": 0x0D, "return": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B,
    "backspace": 0x08, "delete": 0x2E, "del": 0x2E, "space": 0x20,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74, "f6": 0x75,
    "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
}
_EXTENDED = {0x26, 0x28, 0x25, 0x27, 0x24, 0x23, 0x21, 0x22, 0x2E, 0x5B}


def _vk(name: str) -> int | None:
    n = name.strip().lower()
    if n in _VK:
        return _VK[n]
    if len(n) == 1 and n.isalnum() and n.isascii():
        return ord(n.upper())
    return None


def _key_event(vk: int, up: bool):
    flags = (0x0002 if up else 0) | (0x0001 if vk in _EXTENDED else 0)
    user32.keybd_event(vk, 0, flags, 0)


def press_hotkey(combo: str) -> str:
    parts = [p for p in re.split(r"\s*\+\s*", combo.strip().lower()) if p]
    if not parts:
        return "bos kisayol"
    norm = "+".join(parts)
    if norm in BLOCKED_HOTKEYS:
        raise PermissionError(f"'{norm}' kisayolu guvenlik icin engelli.")
    codes = []
    for p in parts:
        code = _vk(p)
        if code is None:
            raise ValueError(f"bilinmeyen tus: {p}")
        codes.append(code)
    for c in codes:
        _key_event(c, False)
        time.sleep(0.03)
    for c in reversed(codes):
        _key_event(c, True)
        time.sleep(0.03)
    return norm


def type_text(text: str):
    """Unicode (Turkce karakterler dahil) yazar."""
    for ch in text:
        if ch == "\n":
            press_hotkey("enter")
            continue
        data = ch.encode("utf-16-le")
        for i in range(0, len(data), 2):
            unit = int.from_bytes(data[i:i + 2], "little")
            for flags in (0x0004, 0x0004 | 0x0002):
                inp = _INPUT(type=1)
                inp.ii.ki = _KEYBDINPUT(0, unit, flags, 0, None)
                user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))
        time.sleep(0.012)


def _screen_size() -> tuple[int, int]:
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def _mouse_click(x: int, y: int, button: str = "left", double: bool = False):
    w, h = _screen_size()
    x = max(12, min(w - 12, int(x)))     # sol-ust acil durdurma kosesine asla gitme
    y = max(12, min(h - 12, int(y)))
    user32.SetCursorPos(x, y)
    time.sleep(0.12)
    down, up = (0x0002, 0x0004) if button == "left" else (0x0008, 0x0010)
    for _ in range(2 if double else 1):
        user32.mouse_event(down, 0, 0, 0, 0)
        time.sleep(0.04)
        user32.mouse_event(up, 0, 0, 0, 0)
        time.sleep(0.08)


def _scroll(amount: int):
    user32.mouse_event(0x0800, 0, 0, ctypes.c_ulong((amount * 120) & 0xFFFFFFFF).value, 0)


def _screenshot_jpeg() -> tuple[bytes, int, int]:
    from actions.screen_vision import _grab_region, _ensure_dpi_awareness
    try:
        _ensure_dpi_awareness()
    except Exception:
        pass
    w, h = _screen_size()
    img = _grab_region(0, 0, w, h)
    if img.width > SHOT_MAX_W:
        ratio = SHOT_MAX_W / img.width
        img = img.resize((SHOT_MAX_W, int(img.height * ratio)))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=70)
    return buf.getvalue(), w, h


# ── Beyin: Gemini'ye "sonraki adim ne?" sor ──────────────────────────────────
_SYSTEM = """Sen bir Windows bilgisayari fare ve klavye ile kullanan ajansin. Ekran goruntusune bakip
kullanicinin hedefine ulasmak icin TEK BIR sonraki adimi secersin.

SADECE su JSON'u dondur (baska hicbir sey yazma). HIZLI olmak icin, sonucu onceden belli
ardisik adimlari TEK cevapta "steps" listesi olarak ver (en fazla 4):
{"thought": "kisa Turkce dusunce",
 "steps": [ {"action": "...", "x": 0-1000, "y": 0-1000, "text": "", "keys": "",
             "amount": 0, "url": "", "enter": false, "risky": false, "message": ""} ]}

ZINCIR KURALI: Ornegin arama kutusuna click -> type(enter:true) tek cevapta olabilir.
Ama ekranin DEGISECEGI bir adimdan (open_url, link/butona click, Enter ile arama) SONRA
zinciri bitir; yeni ekrani gormeden sonraki adimi tahmin etme.
Her adimin ONCESI KURALLARI "risky" icin asagida.

action degerleri:
- open_url : "url" alanindaki siteyi tarayicida ac
- click / double_click / right_click : (x,y) ekran goruntusunun 0-1000 normalize koordinati (x soldan saga, y yukaridan asagi)
- type : "text" yaz (once ilgili kutuya click et). "enter": true ise sonra Enter'a bas
- key : tek tus ("enter","tab","esc","backspace","down"...)
- hotkey : "keys" ornek "ctrl+l", "ctrl+t", "ctrl+f", "alt+left"
- scroll : "amount" pozitif=yukari, negatif=asagi (ornek -5)
- wait : sayfa yuklenmesini bekle
- ask_user : kullaniciya soru sor ("message")
- done : gorev TAMAM, "message" kisa sonuc ozeti (Turkce)
- fail : yapilamiyor, "message" sebep

KESIN KURALLAR:
- Geri alinamaz her adimi ("Satin al", "Ode", "Gonder", "Sil", "Paylas", "Yayinla", "Onayla",
  "Kabul et", para transferi, hesap degisikligi) yapmadan ONCE "risky": true koy ve "message"e
  ne yapacagini yaz. Sistem kullaniciya sorar.
- Sifre, kart numarasi, CVV, SMS/dogrulama kodu, kimlik numarasi ASLA yazma. Gerekirse ask_user.
- CAPTCHA'yi cozmeye calisma, ask_user de.
- Ekranda KADO penceresi (yesil, "K.A.D.O") varsa onu yoksay; gerekirse once open_url ile tarayiciyi one getir.
- Ayni basarisiz adimi tekrarlama; farkli bir yol dene. Hedefe ulastiysan hemen "done" de.
- Yalnizca goruntude GERCEKTEN gordugun ogelere tikla."""


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise ValueError("JSON bulunamadi")
    return json.loads(m.group(0))


def _ask_model(goal: str, history: list[str], jpeg: bytes) -> dict:
    from google import genai
    from google.genai import types

    api_key = str(get_app_config_value("gemini_api_key", "") or "").strip()
    if not api_key:
        raise RuntimeError("Gemini API anahtari yok.")
    client = genai.Client(api_key=api_key)
    hist = "\n".join(f"{i+1}. {h}" for i, h in enumerate(history[-8:])) or "(henuz adim yok)"
    prompt = f"{_SYSTEM}\n\nGOREV: {goal}\n\nONCEKI ADIMLAR:\n{hist}\n\nSimdi ekrana bak ve sonraki adimi ver."
    global _WORKING_MODEL
    last = None

    def _try(models: list[str]):
        nonlocal last
        global _WORKING_MODEL, _THINK_OK
        for model in models:
            for attempt in range(3):
                try:
                    cfg = dict(temperature=0.1, response_mime_type="application/json")
                    if _THINK_OK:
                        cfg["thinking_config"] = types.ThinkingConfig(thinking_level="low")
                    r = client.models.generate_content(
                        model=model,
                        contents=[types.Part.from_text(text=prompt),
                                  types.Part.from_bytes(data=jpeg, mime_type="image/jpeg")],
                        config=types.GenerateContentConfig(**cfg),
                    )
                    out = _extract_json(r.text)
                    _WORKING_MODEL = model
                    return out
                except Exception as e:  # noqa: BLE001
                    last = e
                    msg = str(e).lower()
                    if _THINK_OK and "thinking" in msg:
                        _THINK_OK = False          # bu surum/model desteklemiyor → ayarsiz tekrar dene
                        continue
                    if _is_not_found(e):
                        break                      # bu model yok → siradakine gec
                    if any(k in msg for k in ("quota", "429", "resource exhausted", "rate")):
                        time.sleep(6 * (attempt + 1))
                        continue
                    if any(k in msg for k in ("503", "unavailable", "overloaded", "timeout")):
                        time.sleep(2 * (attempt + 1))
                        continue
                    if isinstance(e, (ValueError, json.JSONDecodeError)):
                        continue
                    break
        return None

    custom = str(get_app_config_value("computer_model", "") or "").strip()
    if custom and not custom.startswith("models/"):
        custom = "models/" + custom
    base = ([custom] if custom else []) + ([_WORKING_MODEL] if _WORKING_MODEL else []) + list(VISION_MODELS)
    order = list(dict.fromkeys(base))
    res = _try(order)
    if res is None and last is not None and _is_not_found(last):
        res = _try([m for m in _discover_models(client) if m not in order])
    if res is not None:
        return res
    raise RuntimeError(f"Gemini yanit vermedi ({str(last)[:150]})")


# ── Gorev yoneticisi ─────────────────────────────────────────────────────────
class ComputerAgent:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._reply_evt = threading.Event()
        self._reply_text = ""
        self.running = False
        self.goal = ""
        self.last_step = ""
        self.question = ""
        self.result = ""

    # -- dis arayuz
    def start(self, goal: str, notify, on_start=None, on_end=None) -> str:
        if self.running:
            return "Zaten bir bilgisayar gorevi suruyor: " + self.goal
        goal = (goal or "").strip()
        if not goal:
            return "Gorev bos."
        self._stop.clear()
        self._reply_evt.clear()
        self.goal, self.last_step, self.question, self.result = goal, "", "", ""
        self.running = True
        self._thread = threading.Thread(
            target=self._run, args=(goal, notify, on_start, on_end), daemon=True)
        self._thread.start()
        return "Gorev basladi. Bitince ya da bir sey sormam gerekince haber verecegim."

    def stop(self) -> str:
        if not self.running:
            return "Calisan bir bilgisayar gorevi yok."
        self._stop.set()
        self._reply_evt.set()
        return "Gorevi durduruyorum."

    def reply(self, answer: str) -> str:
        if not self.running or not self.question:
            return "Cevap bekleyen bir soru yok."
        self._reply_text = (answer or "").strip()
        self._reply_evt.set()
        return "Cevabi ilettim, devam ediyorum."

    def status(self) -> str:
        if not self.running:
            return f"Calisan gorev yok. Son sonuc: {self.result or '-'}"
        if self.question:
            return f"Gorev '{self.goal}' kullanicinin cevabini bekliyor. Soru: {self.question}"
        return f"Gorev suruyor: '{self.goal}'. Son adim: {self.last_step or 'basliyor'}"

    # -- ic isler
    def _emergency(self) -> bool:
        class _PT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        pt = _PT()
        user32.GetCursorPos(ctypes.byref(pt))
        if pt.x <= 3 and pt.y <= 3:
            return True
        return bool(user32.GetAsyncKeyState(0x1B) & 0x8000)   # ESC basili

    def _sleep(self, secs: float) -> bool:
        """Beklerken acil durdurma kontrolu. True donerse durdur."""
        end = time.time() + secs
        esc_since = None
        while time.time() < end:
            if self._stop.is_set():
                return True
            if self._emergency():
                esc_since = esc_since or time.time()
                if time.time() - esc_since > 0.8:
                    self._stop.set()
                    return True
            else:
                esc_since = None
            time.sleep(0.08)
        return False

    def _ask_and_wait(self, question: str, notify) -> str | None:
        self.question = question
        self._reply_evt.clear()
        self._reply_text = ""
        notify(question)
        got = self._reply_evt.wait(CONFIRM_TIMEOUT)
        self.question = ""
        if self._stop.is_set() or not got:
            return None
        return self._reply_text

    def _exec_one(self, a: dict, thought: str, sw: int, sh: int, notify, history: list) -> tuple[str, str]:
        """Tek adimi calistirir. Donus: (durum, mesaj)  durum: ok | stop | skip"""
        action = str(a.get("action", "")).strip().lower()

        if a.get("risky") and action not in ("done", "fail", "ask_user"):
            q = (str(a.get("message") or thought or "Bu adimi yapayim mi?") + " Onayliyor musun?")
            ans = self._ask_and_wait(q, notify)
            if ans is None:
                return "stop", "Onay gelmedi, gorevi durdurdum."
            low = ans.lower()
            denied = re.search(r"hay[ıi]r|yapma|olmaz|iptal|\bdur\b|vazge", low)
            agreed = re.search(r"\b(evet|tamam|onay|olur|yap|devam|ok|tabii|tabi)\b", low)
            if denied or not agreed:
                history.append(f"{action} ONAYLANMADI (kullanici: {ans})")
                return "skip", ""

        try:
            if action == "done":
                return "stop", str(a.get("message") or "Gorev tamam.")
            if action == "fail":
                return "stop", "Yapamadim: " + str(a.get("message") or thought)
            if action == "ask_user":
                ans = self._ask_and_wait(str(a.get("message") or "Ne yapmami istersin?"), notify)
                if ans is None:
                    return "stop", "Cevap gelmedi, gorevi durdurdum."
                history.append(f"ask_user -> kullanici cevabi: {ans}")
                return "skip", ""
            if action == "open_url":
                url = str(a.get("url") or "").strip()
                if not re.match(r"^https?://", url, re.I):
                    url = "https://" + url
                webbrowser.open(url)
            elif action in ("click", "double_click", "right_click"):
                x = float(a.get("x", 500)) / 1000.0 * sw
                y = float(a.get("y", 500)) / 1000.0 * sh
                _mouse_click(x, y, "right" if action == "right_click" else "left",
                             double=(action == "double_click"))
            elif action == "type":
                type_text(str(a.get("text") or ""))
                if a.get("enter"):
                    time.sleep(0.15)
                    press_hotkey("enter")
            elif action == "key":
                press_hotkey(str(a.get("keys") or a.get("text") or "enter"))
            elif action == "hotkey":
                press_hotkey(str(a.get("keys") or ""))
            elif action == "scroll":
                _scroll(int(a.get("amount") or -5))
            elif action == "wait":
                pass
            else:
                history.append(f"gecersiz action: {action}")
                return "skip", ""
            history.append(f"{action} {thought}")
        except PermissionError as e:
            history.append(f"ENGELLENDI: {e}")
        except Exception as e:  # noqa: BLE001
            history.append(f"HATA {action}: {e}")
        return "ok", ""

    def _run(self, goal, notify, on_start, on_end):
        history: list[str] = []
        outcome = ""
        try:
            if on_start:
                try:
                    on_start()
                except Exception:
                    pass
            time.sleep(0.5)
            repeats = 0
            last_sig = ""
            for turn in range(1, MAX_STEPS + 1):
                if self._stop.is_set():
                    outcome = "Gorev durduruldu."
                    break
                jpeg, sw, sh = _screenshot_jpeg()
                t0 = time.time()
                resp = _ask_model(goal, history, jpeg)
                thought = str(resp.get("thought", "")).strip()
                steps = resp.get("steps")
                if not isinstance(steps, list) or not steps:
                    steps = [resp]                       # eski tek-adim formati
                steps = [x for x in steps if isinstance(x, dict)][:MAX_CHAIN]
                print(f"[KADO-PC] tur {turn} ({time.time()-t0:.1f}sn model): {steps}")

                sig = json.dumps(steps, sort_keys=True, ensure_ascii=False)
                repeats = repeats + 1 if sig == last_sig else 0
                last_sig = sig
                if repeats >= 2:
                    outcome = "Ayni adimda takildim, gorevi birakiyorum."
                    break

                stop_now = False
                for idx, a in enumerate(steps):
                    action = str(a.get("action", "")).strip().lower()
                    self.last_step = f"{action}: {thought}"[:160]
                    status, msg = self._exec_one(a, thought, sw, sh, notify, history)
                    if status == "stop":
                        outcome, stop_now = msg, True
                        break
                    if status == "skip":
                        break                            # zinciri bitir, yeni ekrana bak
                    last = (idx == len(steps) - 1)
                    d = DELAYS.get(action, 0.8)
                    if a.get("enter") and action == "type":
                        d = max(d, 1.5)
                    if self._sleep(d if last else min(d, CHAIN_DELAY)):
                        outcome, stop_now = "Gorev durduruldu.", True
                        break
                if stop_now:
                    break
            else:
                outcome = "Adim sinirina ulastim, gorev yarim kalmis olabilir."
        except Exception as e:  # noqa: BLE001
            print(f"[KADO-PC] hata: {e}")
            outcome = f"Gorev hata verdi: {str(e)[:140]}"
        finally:
            self.running = False
            self.question = ""
            self.result = outcome
            if on_end:
                try:
                    on_end()
                except Exception:
                    pass
            try:
                notify(outcome or "Gorev bitti.")
            except Exception:
                pass


AGENT = ComputerAgent()
