#!/usr/bin/env python3


"""


KADO macOS — Gercek zamanli sesli yardimci cekirdegi


macOS ortamina uyarlanmis calisma akisi


"""





import asyncio


import datetime


import threading


import traceback


import os


import subprocess


import sys


import time


import re


from pathlib import Path





from actions.platform_utils import (


    IS_WIN,


    acquire_single_instance,


    attach_parent_console,


    configure_console_output,


    focus_window,


)





# Konsol ciktisini pythonw (konsolsuz) ve Turkce kod sayfasi icin guvenli yap.


# Diger importlardan once calismali — bazi moduller import aninda yazdirir.


configure_console_output()





import pyaudio


import psutil


from google import genai


from google.genai import types





from app_config import get_app_config_value


from ui import KadoUI


from memory.memory_manager import load_memory, update_memory, delete_memory, format_memory_for_prompt


from actions.open_app import open_app


from actions.sys_info  import sys_info


from actions.calendar import get_calendar_events, add_calendar_event, delete_calendar_event


from actions.reminders import get_reminders, add_reminder


from actions.browser   import browser_control


from actions.shell     import shell_run


from actions.whatsapp  import send_whatsapp_message, save_whatsapp_contact


from actions.media     import play_media, control_media


from actions.weather   import get_weather_summary


from actions.screen_vision import analyze_screen


from actions.youtube_stats import get_youtube_channel_report


from actions.computer_agent import AGENT as PC_AGENT


from actions.kado_agent import JOBS, quick_research


from actions import kado_brain


from actions import phone_notify


from actions import sing as sing_mod





# ── Paths ───────────────────────────────────────────────────────────────────


from app_paths import resource_path





BASE_DIR        = Path(__file__).resolve().parent


PROMPT_PATH     = resource_path("core", "prompt.txt")








# ── WebcamStreamer ──────────────────────────────────────────────────────────


class WebcamStreamer:


    """


    Webcam'dan sürekli kare çeker ve en güncel JPEG'i bellekte tutar.


    Queue yerine tek bir 'latest frame' yaklaşımı — eski kare birikimi olmaz.


    """





    JPEG_QUALITY = 72


    MAX_DIM      = 640


    WARMUP       = 6


    # Gecici okuma hatalari normaldir (USB kamera, guc tasarrufu, baska


    # uygulamanin kisa erisimi). Tek hatada akisi kapatmak yerine tolere et.


    MAX_READ_FAILURES = 30


    OPEN_ATTEMPTS = 3


    CAPTURE_INTERVAL = 0.05   # ~20 FPS yakalama (CPU dostu)





    def __init__(self):


        self._latest: bytes | None = None


        self._lock   = threading.Lock()


        self._active = False


        self._thread: threading.Thread | None = None





    @property


    def is_active(self) -> bool:


        return self._active





    def get_latest_frame(self) -> bytes | None:


        """Thread-safe, her zaman en güncel kareyi döner."""


        with self._lock:


            return self._latest





    def start(self) -> str:


        with self._lock:


            if self._active:


                return "already_active"





        # Onceki cekim thread'i kamerayi serbest birakana kadar BEKLE.


        # Beklemezsek yeni VideoCapture "cihaz mesgul" diye acilamiyordu ve


        # kamera kapatilip acildiktan sonra bir daha calismiyordu.


        previous = self._thread


        if previous and previous.is_alive():


            previous.join(timeout=3.0)





        with self._lock:


            self._active = True


            self._latest = None


        t = threading.Thread(target=self._run, daemon=True)


        self._thread = t


        t.start()


        return "ok"





    def stop(self):


        with self._lock:


            self._active = False


            self._latest = None





    def _open_capture(self, cv2):


        """


        Kamerayi acar. Windows'ta DirectShow varsayilandan belirgin hizli


        acilir (~1 sn). Kamera bir onceki oturumdan henuz serbest kalmamis


        olabilecegi icin birkac kez denenir.


        """


        backends = []


        if IS_WIN:


            backends.append(("DirectShow", lambda: cv2.VideoCapture(0, cv2.CAP_DSHOW)))


        backends.append(("varsayilan", lambda: cv2.VideoCapture(0)))





        for attempt in range(1, self.OPEN_ATTEMPTS + 1):


            for label, factory in backends:


                try:


                    cap = factory()


                except Exception:


                    continue


                if cap is not None and cap.isOpened():


                    return cap


                try:


                    if cap is not None:


                        cap.release()


                except Exception:


                    pass


            if attempt < self.OPEN_ATTEMPTS:


                # Kamerayi baska bir surec/onceki thread hala tutuyor olabilir


                time.sleep(0.6)


        return None





    def _run(self):


        try:


            import cv2


        except ImportError:


            print("[Webcam] opencv-python yüklü değil.")


            with self._lock:


                self._active = False


            return





        cap = self._open_capture(cv2)


        if cap is None:


            print("[Webcam] Kamera açılamadı.")


            with self._lock:


                self._active = False


            return





        # Isınma — sensörün otomatik pozlaması oturuncaya kadar bekle


        for _ in range(self.WARMUP):


            cap.read()





        enc_params = [cv2.IMWRITE_JPEG_QUALITY, self.JPEG_QUALITY]


        read_failures = 0





        try:


            while True:


                with self._lock:


                    if not self._active:


                        break





                ret, frame = cap.read()


                if not ret or frame is None:


                    # Tek basarisiz okuma akisi oldurmesin — bir sure dene


                    read_failures += 1


                    if read_failures >= self.MAX_READ_FAILURES:


                        print("[Webcam] Kameradan kare alinamiyor, akis durduruldu.")


                        break


                    time.sleep(0.05)


                    continue


                read_failures = 0





                h, w = frame.shape[:2]


                if max(h, w) > self.MAX_DIM:


                    s = self.MAX_DIM / max(h, w)


                    frame = cv2.resize(frame, (int(w * s), int(h * s)))





                frame = cv2.flip(frame, 1)  # yatay ayna — hem UI hem AI tutarlı


                ok, buf = cv2.imencode(".jpg", frame, enc_params)


                if ok:


                    with self._lock:


                        self._latest = buf.tobytes()





                # ~20 FPS yakala. Onceden 33 FPS'ti ama her kare JPEG'e


                # kodlandigi icin bosuna CPU yiyordu; UI onizlemesi icin


                # 20 FPS gozle ayirt edilemeyecek kadar akici.


                time.sleep(self.CAPTURE_INTERVAL)


        finally:


            cap.release()


            with self._lock:


                self._active = False


                self._latest = None


            print("[Webcam] Kamera serbest bırakıldı.")








CONTROL_TOKEN_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)





# ── Model ───────────────────────────────────────────────────────────────────


LIVE_MODEL = "models/gemini-2.5-flash-native-audio-latest"





# Webcam acikken modele kac saniyede bir kare gonderilecek.


# 0.5 sn = akici "canli goruyor" hissi. Bilgisayar zorlanirsa (eski makine,


# yuksek CPU) bu degeri 1.0-1.5'e cikarmak yeterlidir.


WEBCAM_SEND_INTERVAL = 0.5





# ── Audio ───────────────────────────────────────────────────────────────────


FORMAT           = pyaudio.paInt16


CHANNELS         = 1


SEND_SAMPLE_RATE = 16000


RECV_SAMPLE_RATE = 24000


CHUNK_SIZE       = 1024


pya              = pyaudio.PyAudio()





# ── Tool tanımları — paylaşılan modülden ────────────────────────────────────


from tool_defs import TOOL_DECLARATIONS








def get_api_key() -> str:


    return str(get_app_config_value("gemini_api_key", "") or "")








def load_system_prompt() -> str:


    # Prompt tek dosyada tutulur; Windows'a uyarlamayi prompt_loader yapar.


    from prompt_loader import load_system_prompt as _load





    return _load()








class KadoLive:


    def __init__(self, ui: KadoUI):


        self.ui             = ui


        self.session        = None


        self.audio_in_queue = None


        self.out_queue      = None


        self._loop          = None


        self._is_speaking   = False


        self._el_queue      = None


        self._el_on         = False


        self._el_busy       = False


        self._el_pending    = ""


        self._el_played     = False


        self._el_first      = True


        self._speaking_lock = threading.Lock()


        self._music_proc    = None


        self._webcam_streamer = WebcamStreamer()





        self.ui.on_text_command  = self._on_text_command


        self.ui.on_pause_toggle  = self._on_pause_toggle


        self.ui.on_effects_state_change = self._on_effects_state_change


        self.ui.on_webcam_toggle = self._on_webcam_toggle_ui


        self._paused             = False





    def _on_pause_toggle(self, paused: bool):


        self._paused = paused


        if paused:


            self._stop_music()





    def _on_effects_state_change(self, enabled: bool):


        if not enabled:


            self._stop_music()





    def _on_webcam_toggle_ui(self, activate: bool):


        if activate:


            status = self._webcam_streamer.start()


            self.ui.set_webcam_active(status == "ok" or status == "already_active")


        else:


            self._webcam_streamer.stop()


            self.ui.set_webcam_active(False)





    def _focus_ui_section_for_tool(self, tool_name: str, args: dict):


        if tool_name == "sys_info":


            query = str(args.get("query", "")).strip().lower()


            if query in {"time", "saat", "zaman", "date", "tarih"}:


                self.ui.focus_panel("time", duration_ms=5200)


            else:


                self.ui.focus_panel("system", duration_ms=5200)


        elif tool_name == "get_weather":


            self.ui.focus_panel("weather", duration_ms=5600)





    def _on_text_command(self, text: str):


        if self._paused:


            return


        self.ui.write_log(f"Siz: {text}")


        if not self._loop or not self.session:


            self.ui.write_log("ERR: KADO bağlantısı henüz hazır değil.")


            return


        asyncio.run_coroutine_threadsafe(


            self.session.send_client_content(


                turns={"parts": [{"text": text}]},


                turn_complete=True


            ),


            self._loop


        )





    async def _interrupt_audio(self):


        try:


            if self.audio_in_queue:


                while not self.audio_in_queue.empty():


                    try:


                        self.audio_in_queue.get_nowait()


                    except Exception:


                        break


            if self.session:


                await self.session.send_realtime_input(audio_stream_end=True)


            self.set_speaking(False)


        except Exception:


            pass





    def _stop_music(self):


        proc = self._music_proc


        if proc and proc.poll() is None:


            try:


                proc.terminate()


            except Exception:


                pass


        self._music_proc = None





    def set_speaking(self, value: bool):


        with self._speaking_lock:


            self._is_speaking = value


        if value:


            self.ui.set_state("SPEAKING")


        else:


            self.ui.set_state("LISTENING")





    def speak_error(self, tool_name: str, error: str):


        short = str(error)[:120]


        self.ui.write_log(f"ERR: {tool_name} — {short}")


        self.ui.write_debug(f"{tool_name}: {short}", level="ERROR")


        self.ui.set_state("ERROR")





    @staticmethod


    def _result_looks_like_error(result) -> bool:


        text = str(result or "").strip().lower()


        if not text:


            return False


        error_markers = (


            "hata",


            "error",


            "alinamadi",


            "alınamadı",


            "bulunamadi",


            "bulunamadı",


            "acilamadi",


            "açılamadı",


            "tamamlanamadi",


            "tamamlanamadı",


            "gecersiz",


            "geçersiz",


            "izin gerekiyor",


            "izin gerekli",


            "baglanti",


            "bağlantı",


            "gerekli.",


        )


        return any(marker in text for marker in error_markers)





    @staticmethod


    def _should_play_success_sfx(tool_name: str, args: dict, result) -> bool:


        action_tools = {


            "open_app",


            "add_calendar_event",


            "add_reminder",


            "delete_calendar_event",


            "remove_calendar_event",


        }


        if tool_name in action_tools:


            return True





        if tool_name == "send_whatsapp_message":


            text = str(result or "").lower()


            if bool(args.get("send_now", False)):


                return "gönderildi" in text or "gonderildi" in text


            return False





        return False





    @staticmethod


    def _clean_transcript_text(text: str) -> tuple[str, bool]:


        raw = str(text or "")


        had_noise = False


        if CONTROL_TOKEN_RE.search(raw):


            had_noise = True


            raw = CONTROL_TOKEN_RE.sub(" ", raw)


        cleaned = []


        for ch in raw:


            if ch in "\n\r\t" or ord(ch) >= 32:


                cleaned.append(ch)


            else:


                had_noise = True


        normalized = " ".join("".join(cleaned).split())


        return normalized.strip(), had_noise





    # ── ElevenLabs ses ───────────────────────────────────────────────────────


    def _el_refresh(self):


        key = str(get_app_config_value("elevenlabs_api_key", "") or "").strip()


        vid = str(get_app_config_value("elevenlabs_voice_id", "") or "").strip()


        self._el_on = bool(key and vid)


        return self._el_on





    def _el_flush(self, force: bool = False):


        """Biriken metinden tamamlanan cümleleri ElevenLabs kuyruğuna at."""


        if not self._el_on or self._el_queue is None:


            return


        buf = self._el_pending


        if force:


            cut = len(buf)


        else:


            ends = [m.end() for m in re.finditer(r"[.!?…:](?=\s|$)", buf)]


            cut = ends[-1] if ends else 0


            if not cut and self._el_first and len(buf) >= 40:


                # Cevabin ILK parcasi: cumle bitmesini bekleme, virgulde hemen konusmaya basla


                commas = [m.end() for m in re.finditer(r"[,;—](?=\s)", buf)]


                cut = commas[-1] if commas else 0


        chunk, self._el_pending = buf[:cut].strip(), buf[cut:]


        if chunk:


            self._el_first = False


            self._el_queue.put_nowait(chunk)





    def _el_stream_blocking(self, text: str, loop):


        import requests


        key   = str(get_app_config_value("elevenlabs_api_key", "")).strip()


        vid   = str(get_app_config_value("elevenlabs_voice_id", "")).strip()


        model = str(get_app_config_value("elevenlabs_model", "eleven_flash_v2_5") or "eleven_flash_v2_5")


        resp = None


        for attempt in range(4):


            resp = requests.post(


                f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/stream",


                params={"output_format": "pcm_24000"},


                headers={"xi-api-key": key, "Content-Type": "application/json"},


                json={"text": text, "model_id": model},


                stream=True, timeout=30,


            )


            if resp.status_code == 429:          # es zamanli istek siniri → kisa bekle, tekrar dene


                time.sleep(1.0 * (attempt + 1))


                continue


            break


        if resp.status_code != 200:


            raise RuntimeError(f"ElevenLabs {resp.status_code}: {resp.text[:200]}")


        leftover = b""


        for part in resp.iter_content(chunk_size=4096):


            if not part:


                continue


            data = leftover + part


            if len(data) % 2:


                leftover, data = data[-1:], data[:-1]


            else:


                leftover = b""


            if data:


                loop.call_soon_threadsafe(self.audio_in_queue.put_nowait, data)





    async def _elevenlabs_worker(self):


        loop = asyncio.get_running_loop()


        while True:


            text = await self._el_queue.get()


            self._el_busy = True


            try:


                await asyncio.to_thread(self._el_stream_blocking, text, loop)


            except Exception as e:


                print(f"[KADO] ❌ ElevenLabs: {e}")


                self.ui.write_log(f"ERR: ElevenLabs sesi çalışmadı ({str(e)[:120]}). Windows sesiyle devam ediyorum.")


                try:


                    from actions.tts import speak_text


                    speak_text(text)


                except Exception:


                    pass


            finally:


                self._el_busy = False





    # ── Şarkı söyleme (orijinal sözler, enstrümansız) ────────────────────────


    def _sing_worker(self, request: str, style: str, lyrics: str):


        try:


            self._el_played = True


            for pcm in sing_mod.perform(request, style, lyrics):


                if self._loop is not None:


                    self._loop.call_soon_threadsafe(self.audio_in_queue.put_nowait, pcm)


        except Exception as e:  # noqa: BLE001


            print(f"[KADO] ❌ şarkı: {e}")


            self._pc_notify(f"Şarkıda bir sorun çıktı: {str(e)[:120]}")





    # ── Bilgisayar görevi bildirimleri ───────────────────────────────────────











    async def _agent_notification_voice_test(self):


        """Yalnizca manuel cagirilacak ses testi."""


        message = (


            "Reis, bu bir Kado ajan bildirim testidir. "


            "Sesli bildirim sistemi calisiyor."


        )





        if self._el_on and self._el_queue is not None:


            await self._el_queue.put(message)


        else:


            from actions.tts import speak_text


            await asyncio.to_thread(speak_text, message)








    async def _agent_meeting_notifier(self):


        """Yeni tamamlanan toplantilari ayri ayri takip eder."""


        import sqlite3


        import json


        from pathlib import Path





        root = Path(r"C:\KADO\KADO-AJANLAR")


        db = root / "memory" / "kado_company.db"


        state = root / "memory" / "kado_notifier_v3.json"


        old_state = root / "memory" / "kado_notifier_seen.txt"





        def read_meetings():


            con = sqlite3.connect(


                f"file:{db.as_posix()}?mode=ro",


                uri=True,


                timeout=3


            )


            try:


                return con.execute(


                    "SELECT id, status FROM meetings ORDER BY id"


                ).fetchall()


            finally:


                con.close()





        def save_state(data):


            temp = state.with_suffix(".tmp")


            temp.write_text(


                json.dumps(data, ensure_ascii=False),


                encoding="utf-8"


            )


            temp.replace(state)





        if state.exists():


            data = json.loads(state.read_text(encoding="utf-8"))


        else:


            rows = await asyncio.to_thread(read_meetings)


            baseline = max((mid for mid, _ in rows), default=0)





            if old_state.exists():


                baseline = max(


                    baseline,


                    int(old_state.read_text(encoding="utf-8").strip())


                )





            data = {


                "baseline": baseline,


                "notified": []


            }


            save_state(data)





        while True:


            try:


                rows = await asyncio.to_thread(read_meetings)


                baseline = int(data["baseline"])


                notified = set(data["notified"])





                for mid, status in rows:


                    if mid <= baseline or status != "completed":


                        continue


                    if mid in notified:


                        continue





                    # Tekrar bildirim riskini azaltmak icin


                    # ses kuyru?una eklemeden once kaydet.


                    notified.add(mid)


                    data["notified"] = sorted(notified)


                    save_state(data)





                    message = (


                        "Reis, ekip toplantiyi bitirdi. "


                        "Dort ajanin raporu hazir. "


                        "Istersen sonuclari anlatayim."


                    )





                    try:


                        self.ui.write_log(


                            f"KADO: Toplanti #{mid} tamamlandi."


                        )


                    except Exception:


                        pass





                    if self._el_on and self._el_queue is not None:


                        await self._el_queue.put(message)


                    else:


                        from actions.tts import speak_text


                        await asyncio.to_thread(speak_text, message)





            except asyncio.CancelledError:


                raise


            except Exception as exc:


                print(f"[KADO] Ajan bildirimi: {exc}")








            await asyncio.sleep(5)





    async def _content_pack_notifier(self):


        """Onay bekleyen yeni icerik paketlerini sesli haber verir."""


        import subprocess


        import json


        import time


        from pathlib import Path





        root = Path(r"C:\KADO\KADO-AJANLAR")


        state = root / "memory" / "kado_icerik_bildirim.json"


        lock = root / "memory" / "nobetci.lock"





        def read_seen():


            try:


                return set(json.loads(state.read_text(encoding="utf-8")).get("seen", []))


            except Exception:


                return set()





        def save_seen(seen):


            try:


                tmp = state.with_suffix(".tmp")


                tmp.write_text(json.dumps({"seen": sorted(seen)}, ensure_ascii=False),


                               encoding="utf-8")


                tmp.replace(state)


            except Exception:


                pass





        def pending():


            r = subprocess.run([r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe", r"C:\KADO\KADO-AJANLAR\kado_onay.py", "listele"],


                               capture_output=True, text=True, encoding="utf-8",


                               errors="replace", timeout=20, check=False,


                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


            out = []


            for ln in (r.stdout or "").splitlines():


                if not ln.startswith("- "):


                    continue


                p = [x.strip() for x in ln[2:].split(" | ")]


                if len(p) >= 3:


                    out.append((p[0], p[1], p[2].split(":")[0].strip()))


            return out





        def pipeline_busy():


            try:


                return lock.exists() and (time.time() - lock.stat().st_mtime) < 6 * 3600


            except Exception:


                return False





        await asyncio.sleep(20)


        while True:


            try:


                if not await asyncio.to_thread(pipeline_busy):


                    items = await asyncio.to_thread(pending)


                    seen = read_seen()


                    new = [i for i in items if i[0] not in seen]


                    if new:


                        seen.update(i[0] for i in new)


                        save_seen(seen)


                        if len(new) == 1:


                            message = ("Reis, " + new[0][2] + " icin " + new[0][1] +


                                       " paketi hazir. Yayinlanmadi, onayini bekliyor.")


                        else:


                            message = ("Reis, onayini bekleyen " + str(len(new)) +


                                       " yeni paket var. Hicbir sey yayinlanmadi.")


                        try:


                            self.ui.write_log("KADO: " + message)


                        except Exception:


                            pass


                        if self._el_on and self._el_queue is not None:


                            await self._el_queue.put(message)


                        else:


                            from actions.tts import speak_text


                            await asyncio.to_thread(speak_text, message)


            except asyncio.CancelledError:


                raise


            except Exception as exc:


                print(f"[KADO] Icerik bildirimi: {exc}")


            await asyncio.sleep(30)





    def _pc_notify(self, text: str):


        text = str(text or "").strip()


        if not text:


            return


        try:


            self.ui.write_log(f"KADO: {text}")


        except Exception:


            pass


        try:


            phone_notify.maybe_forward(text)


        except Exception:


            pass


        try:


            if self._el_on and self._el_queue is not None and self._loop is not None:


                self._loop.call_soon_threadsafe(self._el_queue.put_nowait, text)


            else:


                from actions.tts import speak_text


                speak_text(text)


        except Exception:


            pass





    def _pc_on_start(self):


        try:


            self.ui.root.after(0, self.ui.root.iconify)


        except Exception:


            pass





    def _pc_on_end(self):


        try:


            def _back():


                self.ui.root.deiconify()


                self.ui.root.lift()


            self.ui.root.after(0, _back)


        except Exception:


            pass





    def _build_config(self) -> types.LiveConnectConfig:


        import datetime


        memory  = load_memory()


        mem_str = format_memory_for_prompt(memory)


        sys_p   = load_system_prompt()


        now     = datetime.datetime.now()


        time_ctx = f"[ŞU ANKİ ZAMAN]\n{now.strftime('%A, %d %B %Y — %H:%M')}\n\n"





        parts = [time_ctx]


        if mem_str:


            parts.append(mem_str + "\n\n")


        parts.append(sys_p)





        return types.LiveConnectConfig(


            response_modalities=["AUDIO"],


            output_audio_transcription={},


            input_audio_transcription={},


            system_instruction="\n".join(parts),


            tools=[{"function_declarations": TOOL_DECLARATIONS}],


            speech_config=types.SpeechConfig(


                voice_config=types.VoiceConfig(


                    prebuilt_voice_config=types.PrebuiltVoiceConfig(


                        voice_name=str(get_app_config_value("voice", "Charon") or "Charon")


                    )


                )


            ),


        )





    async def _execute_tool(self, fc) -> types.FunctionResponse:


        name = fc.name


        args = dict(fc.args or {})


        print(f"[KADO] 🔧 {name} {args}")


        self.ui.set_state("THINKING")





        loop   = asyncio.get_event_loop()


        result = "Tamam."


        had_exception = False





        try:


            if name == "save_memory":


                cat = str(args.get("category", "") or "notes").strip() or "notes"


                key = str(args.get("key", "") or "").strip()


                val = str(args.get("value", "") or "").strip()


                if not key or not val:


                    # Eskiden bu durumda da "ok" donuyordu; model kaydettigini


                    # saniyor ama hicbir sey yazilmiyordu. Artik durumu bildiriyoruz.


                    result = (


                        "Hafizaya yazilamadi: key ve value dolu olmali. "


                        "Ornek: category='identity', key='name', value='Ahmet'"


                    )


                else:


                    update_memory({cat: {key: {"value": val}}})


                    print(f"[Memory] 💾 {cat}/{key} = {val}")


                    result = f"Hafizaya kaydedildi: {cat}/{key} = {val}"





            elif name == "delete_memory":


                result = delete_memory(


                    args.get("category", ""),


                    args.get("key", ""),


                    args.get("match_text", ""),


                )





            elif name == "open_app":


                r = await loop.run_in_executor(


                    None, lambda: open_app(args.get("app_name", "")))


                result = r or f"{args.get('app_name')} açıldı."





            elif name == "sys_info":


                self._focus_ui_section_for_tool(name, args)


                r = await loop.run_in_executor(


                    None, lambda: sys_info(args.get("query", "all")))


                result = r or "Bilgi alındı."





            elif name == "get_weather":


                self._focus_ui_section_for_tool(name, args)


                r = await loop.run_in_executor(


                    None, lambda: get_weather_summary(args.get("location") or None))


                result = r or "Hava durumu bilgisi alindi."





            elif name == "get_calendar_events":


                r = await loop.run_in_executor(


                    None,


                    lambda: get_calendar_events(


                        args.get("query", "today"),


                        int(args.get("limit", 6) or 6),


                    ),


                )


                result = r or "Takvim bilgisi alindi."





            elif name == "add_calendar_event":


                r = await loop.run_in_executor(


                    None,


                    lambda: add_calendar_event(


                        args.get("title", ""),


                        args.get("start_iso", ""),


                        args.get("end_iso", ""),


                        args.get("notes", ""),


                        args.get("location", ""),


                        args.get("calendar_name", ""),


                        bool(args.get("all_day", False)),


                    ),


                )


                result = r or "Takvim etkinligi eklendi."





            elif name == "delete_calendar_event":


                r = await loop.run_in_executor(


                    None,


                    lambda: delete_calendar_event(


                        args.get("title", ""),


                        args.get("start_iso", ""),


                        args.get("calendar_name", ""),


                        bool(args.get("delete_all_matches", False)),


                    ),


                )


                result = r or "Takvim etkinligi silindi."





            elif name == "get_reminders":


                r = await loop.run_in_executor(


                    None,


                    lambda: get_reminders(


                        args.get("query", "upcoming"),


                        int(args.get("limit", 8) or 8),


                        args.get("list_name", ""),


                    ),


                )


                result = r or "Animsatici bilgisi alindi."





            elif name == "add_reminder":


                r = await loop.run_in_executor(


                    None,


                    lambda: add_reminder(


                        args.get("title", ""),


                        args.get("due_iso", ""),


                        args.get("notes", ""),


                        args.get("list_name", ""),


                        args.get("priority", ""),


                        bool(args.get("all_day", False)),


                    ),


                )


                result = r or "Animsatici eklendi."





            elif name == "browser_control":


                r = await loop.run_in_executor(


                    None, lambda: browser_control(


                        args.get("action"),


                        args.get("url"),


                        args.get("query")


                    ))


                result = r or "Tamam."








            elif name == "create_agent_task":


                import subprocess as _task_sp


                import json as _task_json


                from pathlib import Path as _TaskPath





                _root = _TaskPath("C:/KADO/KADO-AJANLAR")


                _python = _root / ".venv/Scripts/python.exe"


                _bridge = _root / "kado_gorev_koprusu.py"





                def _create_agent_task():


                    title = str(args.get("title", "")).strip()


                    details = str(args.get("details", "")).strip()





                    if not 5 <= len(title) <= 150:


                        return "Gorev basligi 5 ile 150 karakter arasinda olmali."





                    if len(details) > 2000:


                        return "Gorev aciklamasi cok uzun."





                    if not _python.is_file() or not _bridge.is_file():


                        return "Gorev sistemi dosyalari bulunamadi."





                    proc = _task_sp.run(


                        [


                            str(_python),


                            str(_bridge),


                            "create",


                            title,


                            details,


                        ],


                        cwd=str(_root),


                        capture_output=True,


                        text=True,


                        encoding="utf-8",


                        errors="replace",


                        timeout=15,


                    )





                    if proc.returncode != 0:


                        return "Gorev olusturulamadi. Kayit basarisiz."





                    try:


                        data = _task_json.loads(proc.stdout.strip())


                    except Exception:


                        return "Gorev olusturma cevabi okunamadi."





                    if not data.get("ok"):


                        return "Gorev olusturulamadi: " + str(


                            data.get("message", "Bilinmeyen hata")


                        )





                    task_id = data.get("task_id")


                    return (


                        f"Gorev #{task_id} olusturuldu. "


                        "Ajanlar henuz baslatilmadi. "


                        "Ekibi calistirmami ister misin?"


                    )





                result = await loop.run_in_executor(


                    None, _create_agent_task


                )





            elif name == "start_agent_task":


                import subprocess as _agent_sp


                import json as _agent_json


                import sqlite3 as _agent_sqlite


                from pathlib import Path as _AgentPath





                _agent_root = _AgentPath("C:/KADO/KADO-AJANLAR")


                _agent_python = _agent_root / ".venv/Scripts/python.exe"


                _agent_bridge = _agent_root / "kado_api_koprusu.py"


                _agent_db = _agent_root / "memory/kado_company.db"





                def _start_agent_task():


                    try:


                        _task_id = int(args.get("task_id", 0))


                    except (TypeError, ValueError):


                        return "Gecersiz gorev numarasi."





                    if _task_id < 1:


                        return "Baslatmak icin gecerli bir gorev numarasi soyle."





                    if not all(p.is_file() for p in (


                        _agent_python, _agent_bridge, _agent_db


                    )):


                        return "Ajan sistemi dosyalari eksik. Baslatilmadi."





                    with _agent_sqlite.connect(str(_agent_db)) as _db:


                        _task = _db.execute(


                            "SELECT title FROM tasks WHERE id=?",


                            (_task_id,)


                        ).fetchone()


                        if not _task:


                            return (


                                f"Gorev #{_task_id} bulunamadi. "


                                "Ajanlar baslatilmadi."


                            )





                        _meeting = _db.execute(


                            "SELECT id, status FROM meetings "


                            "WHERE topic LIKE ? ORDER BY id DESC LIMIT 1",


                            (f"Panel gorevi #{_task_id}:%",)


                        ).fetchone()





                        if _meeting and _meeting[1] == "completed":


                            return (


                                f"Gorev #{_task_id} icin daha once "


                                f"toplanti #{_meeting[0]} tamamlanmis. "


                                "Yeni toplanti baslatilmadi."


                            )





                    _log_dir = _agent_root / "logs"


                    _log_dir.mkdir(exist_ok=True)





                    _log_path = _log_dir / (


                        f"sesli_gorev_{_task_id}.log"


                    )





                    _log = open(_log_path, "ab")





                    try:


                        _flags = getattr(


                            _agent_sp, "CREATE_NO_WINDOW", 0


                        )





                        _proc = _agent_sp.Popen(


                            [


                                str(_agent_python),


                                str(_agent_bridge),


                                "--task-id",


                                str(_task_id),


                            ],


                            cwd=str(_agent_root),


                            stdin=_agent_sp.DEVNULL,


                            stdout=_log,


                            stderr=_agent_sp.STDOUT,


                            creationflags=_flags,


                        )


                    finally:


                        _log.close()





                    return (


                        f"Gorev #{_task_id} icin ajan baslatma "


                        f"istegi gonderildi. Islem numarasi "


                        f"{_proc.pid}. Toplanti henuz "


                        "tamamlanmadi. Durumunu kontrol edebiliriz."


                    )





                result = await loop.run_in_executor(


                    None, _start_agent_task


                )





            elif name == "get_agent_status":


                import json as _json


                import subprocess as _sp


                from pathlib import Path as _Path





                _root = _Path("C:/KADO/KADO-AJANLAR")


                _python = _root / ".venv/Scripts/python.exe"


                _bridge = _root / "kado_gorev_koprusu.py"





                def _read_status():


                    _r = _sp.run(


                        [str(_python), str(_bridge), "status"],


                        capture_output=True, text=True,


                        encoding="utf-8", errors="replace",


                        timeout=15, check=False


                    )


                    if _r.returncode != 0:


                        return "Ajan durum bilgisi alinamadi."


                    _data = _json.loads(_r.stdout)


                    if not _data.get("ok"):


                        return str(_data.get("message", "Durum alinamadi."))





                    _state = _data.get("agent_state") or {}


                    _task = _data.get("last_task") or {}


                    _meeting = _data.get("last_task_meeting")





                    if not _task:


                        return "Henuz kayitli bir ajan gorevi yok."





                    _id = _task.get("id")


                    _title = _task.get("title", "Bilinmiyor")


                    _status = _task.get("status", "Bilinmiyor")





                    if not _meeting:


                        return (


                            f"Gorev #{_id}: {_title}. "


                            f"Gorev kayit durumu: {_status}. "


                            "Bu gorev icin henuz toplanti yapilmamis. "


                            "Ajanlarin calistigini soyleme."


                        )





                    _phase = _state.get("phase", "Bilinmiyor")


                    _agent = _state.get("agent") or "Bilinmiyor"





                    return (


                        f"Gorev #{_id}: {_title}. "


                        f"Gorev kayit durumu: {_status}. "


                        f"Son toplanti #{_meeting.get('id')}, "


                        f"toplanti durumu: {_meeting.get('status')}. "


                        f"Son durum kaydi: {_phase}. "


                        f"Son ajan: {_agent}. "


                        "Durum kaydi gecmis bir calismaya ait olabilir; "


                        "anlik calisma olarak sunma."


                    )





                result = await loop.run_in_executor(None, _read_status)





            elif name == "get_agent_report":


                import subprocess as _sp


                import sys as _sys


                from pathlib import Path as _Path





                _bridge = _Path(r"C:\KADO\KADO-AJANLAR\kado_ses_koprusu.py")


                _python = _Path(r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe")





                def _read_agent_report():


                    _r = _sp.run(


                        [str(_python), str(_bridge)],


                        capture_output=True,


                        text=True,


                        encoding="utf-8",


                        errors="replace",


                        timeout=15,


                        check=False,


                    )


                    if _r.returncode != 0:


                        return "Ajan raporu okunamadi."


                    import json as _json


                    _data = _json.loads(_r.stdout)


                    if "error" in _data:


                        return str(_data["error"])


                    _reports = _data.get("reports", [])


                    _parts = [


                        "Toplanti: " + str(_data.get("topic", "")),


                        "Toplanti numarasi: " + str(_data.get("meeting_id", "")),


                    ]


                    for _item in _reports:


                        _parts.append(


                            str(_item.get("agent", "")) + ": " +


                            str(_item.get("report", ""))[:1800]


                        )


                    return "\n\n".join(_parts)[:8500]





                result = await loop.run_in_executor(


                    None, _read_agent_report


                )





            elif name == "start_content_task":


                import subprocess as _csp





                def _content_task():


                    _cmd = [r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe", r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py", "baslat",


                            str(args.get("project", ""))]


                    if args.get("again"):


                        _cmd.append("--yeniden")


                    _r = _csp.run(_cmd, capture_output=True, text=True,


                                  encoding="utf-8", errors="replace",


                                  timeout=30, check=False)


                    return (_r.stdout or "").strip() or "Baslatilamadi."





                result = await loop.run_in_executor(None, _content_task)





            elif name == "get_content_status":


                import subprocess as _csp2





                def _content_status():


                    _r = _csp2.run([r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe", r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py", "durum"],


                                   capture_output=True, text=True,


                                   encoding="utf-8", errors="replace",


                                   timeout=40, check=False)


                    return (_r.stdout or "").strip() or "Durum okunamadi."





                result = await loop.run_in_executor(None, _content_status)





            elif name == "prepare_publish_package":


                import subprocess as _psp





                def _publish_pack():


                    _r = _psp.run([r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe", r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py", "yayin"],


                                  capture_output=True, text=True,


                                  encoding="utf-8", errors="replace",


                                  timeout=120, check=False)


                    return (_r.stdout or "").strip() or "Hazirlanamadi."





                result = await loop.run_in_executor(None, _publish_pack)





            elif name == 'kado_project_add':

                import subprocess as _ksp

                def _kado_bridge_call():

                    _py = str(r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe")

                    _bridge = str(r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py")

                    _r = _ksp.run([_py, _bridge, 'proje-ekle', str(args.get('name', "")), str(args.get('goal', ""))], capture_output=True, text=True,

                                 encoding="utf-8", errors="replace", timeout=45, check=False)

                    return (_r.stdout or _r.stderr or "KADO komutu yanit vermedi").strip()[:2500]

                result = await loop.run_in_executor(None, _kado_bridge_call)



            elif name == 'kado_project_list':

                import subprocess as _ksp

                def _kado_bridge_call():

                    _py = str(r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe")

                    _bridge = str(r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py")

                    _r = _ksp.run([_py, _bridge, 'proje-liste'], capture_output=True, text=True,

                                 encoding="utf-8", errors="replace", timeout=45, check=False)

                    return (_r.stdout or _r.stderr or "KADO komutu yanit vermedi").strip()[:2500]

                result = await loop.run_in_executor(None, _kado_bridge_call)



            elif name == 'kado_pending_packages':

                import subprocess as _ksp

                def _kado_bridge_call():

                    _py = str(r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe")

                    _bridge = str(r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py")

                    _r = _ksp.run([_py, _bridge, 'paketler'], capture_output=True, text=True,

                                 encoding="utf-8", errors="replace", timeout=45, check=False)

                    return (_r.stdout or _r.stderr or "KADO komutu yanit vermedi").strip()[:2500]

                result = await loop.run_in_executor(None, _kado_bridge_call)



            elif name == 'kado_read_package':

                import subprocess as _ksp

                def _kado_bridge_call():

                    _py = str(r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe")

                    _bridge = str(r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py")

                    _r = _ksp.run([_py, _bridge, 'oku', str(args.get('target', ""))], capture_output=True, text=True,

                                 encoding="utf-8", errors="replace", timeout=45, check=False)

                    return (_r.stdout or _r.stderr or "KADO komutu yanit vermedi").strip()[:2500]

                result = await loop.run_in_executor(None, _kado_bridge_call)



            elif name == 'kado_approval_request':

                import subprocess as _ksp

                def _kado_bridge_call():

                    _py = str(r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe")

                    _bridge = str(r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py")

                    _r = _ksp.run([_py, _bridge, 'onayla', str(args.get('target', ""))], capture_output=True, text=True,

                                 encoding="utf-8", errors="replace", timeout=45, check=False)

                    return (_r.stdout or _r.stderr or "KADO komutu yanit vermedi").strip()[:2500]

                result = await loop.run_in_executor(None, _kado_bridge_call)



            elif name == 'kado_rejection_request':

                import subprocess as _ksp

                def _kado_bridge_call():

                    _py = str(r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe")

                    _bridge = str(r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py")

                    _r = _ksp.run([_py, _bridge, 'reddet', str(args.get('target', "")), str(args.get('reason', ""))], capture_output=True, text=True,

                                 encoding="utf-8", errors="replace", timeout=45, check=False)

                    return (_r.stdout or _r.stderr or "KADO komutu yanit vermedi").strip()[:2500]

                result = await loop.run_in_executor(None, _kado_bridge_call)



            elif name == 'kado_approval_confirm':

                import subprocess as _ksp

                def _kado_bridge_call():

                    _py = str(r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe")

                    _bridge = str(r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py")

                    _r = _ksp.run([_py, _bridge, 'onayla', str(args.get('target', "")), "--evet"], capture_output=True, text=True,

                                 encoding="utf-8", errors="replace", timeout=45, check=False)

                    return (_r.stdout or _r.stderr or "KADO komutu yanit vermedi").strip()[:2500]

                result = await loop.run_in_executor(None, _kado_bridge_call)



            elif name == 'kado_rejection_confirm':

                import subprocess as _ksp

                def _kado_bridge_call():

                    _py = str(r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe")

                    _bridge = str(r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py")

                    _r = _ksp.run([_py, _bridge, 'reddet', str(args.get('target', "")), "--evet"], capture_output=True, text=True,

                                 encoding="utf-8", errors="replace", timeout=45, check=False)

                    return (_r.stdout or _r.stderr or "KADO komutu yanit vermedi").strip()[:2500]

                result = await loop.run_in_executor(None, _kado_bridge_call)



            elif name == 'kado_undo_decision':

                import subprocess as _ksp

                def _kado_bridge_call():

                    _py = str(r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe")

                    _bridge = str(r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py")

                    _r = _ksp.run([_py, _bridge, 'geri', str(args.get('target', ""))], capture_output=True, text=True,

                                 encoding="utf-8", errors="replace", timeout=45, check=False)

                    return (_r.stdout or _r.stderr or "KADO komutu yanit vermedi").strip()[:2500]

                result = await loop.run_in_executor(None, _kado_bridge_call)



            elif name == 'kado_project_add':
                import subprocess as _ksp
                def _kado_bridge_call():
                    _py = str(r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe")
                    _bridge = str(r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py")
                    _r = _ksp.run([_py, _bridge, 'proje-ekle', str(args.get('name', "")), str(args.get('goal', ""))], capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=45, check=False)
                    return (_r.stdout or _r.stderr or "KADO komutu yanit vermedi").strip()[:2500]
                result = await loop.run_in_executor(None, _kado_bridge_call)

            elif name == 'kado_project_list':
                import subprocess as _ksp
                def _kado_bridge_call():
                    _py = str(r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe")
                    _bridge = str(r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py")
                    _r = _ksp.run([_py, _bridge, 'proje-liste'], capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=45, check=False)
                    return (_r.stdout or _r.stderr or "KADO komutu yanit vermedi").strip()[:2500]
                result = await loop.run_in_executor(None, _kado_bridge_call)

            elif name == 'kado_pending_packages':
                import subprocess as _ksp
                def _kado_bridge_call():
                    _py = str(r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe")
                    _bridge = str(r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py")
                    _r = _ksp.run([_py, _bridge, 'paketler'], capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=45, check=False)
                    return (_r.stdout or _r.stderr or "KADO komutu yanit vermedi").strip()[:2500]
                result = await loop.run_in_executor(None, _kado_bridge_call)

            elif name == 'kado_read_package':
                import subprocess as _ksp
                def _kado_bridge_call():
                    _py = str(r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe")
                    _bridge = str(r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py")
                    _r = _ksp.run([_py, _bridge, 'oku', str(args.get('target', ""))], capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=45, check=False)
                    return (_r.stdout or _r.stderr or "KADO komutu yanit vermedi").strip()[:2500]
                result = await loop.run_in_executor(None, _kado_bridge_call)

            elif name == 'kado_approval_request':
                import subprocess as _ksp
                def _kado_bridge_call():
                    _py = str(r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe")
                    _bridge = str(r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py")
                    _r = _ksp.run([_py, _bridge, 'onayla', str(args.get('target', ""))], capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=45, check=False)
                    return (_r.stdout or _r.stderr or "KADO komutu yanit vermedi").strip()[:2500]
                result = await loop.run_in_executor(None, _kado_bridge_call)

            elif name == 'kado_rejection_request':
                import subprocess as _ksp
                def _kado_bridge_call():
                    _py = str(r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe")
                    _bridge = str(r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py")
                    _r = _ksp.run([_py, _bridge, 'reddet', str(args.get('target', "")), str(args.get('reason', ""))], capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=45, check=False)
                    return (_r.stdout or _r.stderr or "KADO komutu yanit vermedi").strip()[:2500]
                result = await loop.run_in_executor(None, _kado_bridge_call)

            elif name == 'kado_approval_confirm':
                import subprocess as _ksp
                def _kado_bridge_call():
                    _py = str(r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe")
                    _bridge = str(r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py")
                    _r = _ksp.run([_py, _bridge, 'onayla', str(args.get('target', "")), "--evet"], capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=45, check=False)
                    return (_r.stdout or _r.stderr or "KADO komutu yanit vermedi").strip()[:2500]
                result = await loop.run_in_executor(None, _kado_bridge_call)

            elif name == 'kado_rejection_confirm':
                import subprocess as _ksp
                def _kado_bridge_call():
                    _py = str(r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe")
                    _bridge = str(r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py")
                    _r = _ksp.run([_py, _bridge, 'reddet', str(args.get('target', "")), "--evet"], capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=45, check=False)
                    return (_r.stdout or _r.stderr or "KADO komutu yanit vermedi").strip()[:2500]
                result = await loop.run_in_executor(None, _kado_bridge_call)

            elif name == 'kado_undo_decision':
                import subprocess as _ksp
                def _kado_bridge_call():
                    _py = str(r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe")
                    _bridge = str(r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py")
                    _r = _ksp.run([_py, _bridge, 'geri', str(args.get('target', ""))], capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=45, check=False)
                    return (_r.stdout or _r.stderr or "KADO komutu yanit vermedi").strip()[:2500]
                result = await loop.run_in_executor(None, _kado_bridge_call)

            elif name == "kado_assign_task":
                import subprocess as _ksp
                def _ceo_voice_call():
                    _py = str(r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe")
                    _bridge = str(r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py")
                    _r = _ksp.run([_py, _bridge, "gorev", str(args.get("request", ""))], capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", timeout=45, check=False)
                    return (_r.stdout or _r.stderr or "Gorev komutu yanit vermedi").strip()[:2500]
                result = await loop.run_in_executor(None, _ceo_voice_call)

            elif name == "kado_company_overview":
                import subprocess as _ksp
                def _kado_center_call():
                    _py = 'C:\\KADO\\KADO-AJANLAR\\.venv\\Scripts\\python.exe'
                    _center = 'C:\\KADO\\KADO-AJANLAR\\kado_ceo.py'
                    _r = _ksp.run([_py, _center, 'status'], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45, check=False)
                    return (_r.stdout or _r.stderr or "KADO yanit vermedi").strip()[:3500]
                result = await loop.run_in_executor(None, _kado_center_call)

            elif name == "kado_influencer_start":
                import subprocess as _ksp
                def _kado_center_call():
                    _py = 'C:\\KADO\\KADO-AJANLAR\\.venv\\Scripts\\python.exe'
                    _center = 'C:\\KADO\\KADO-AJANLAR\\kado_ceo.py'
                    _r = _ksp.run([_py, _center, 'influencer-init', str(args.get('name', ""))], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45, check=False)
                    return (_r.stdout or _r.stderr or "KADO yanit vermedi").strip()[:3500]
                result = await loop.run_in_executor(None, _kado_center_call)

            elif name == "kado_influencer_calendar":
                import subprocess as _ksp
                def _kado_center_call():
                    _py = 'C:\\KADO\\KADO-AJANLAR\\.venv\\Scripts\\python.exe'
                    _center = 'C:\\KADO\\KADO-AJANLAR\\kado_ceo.py'
                    _r = _ksp.run([_py, _center, 'influencer-plan'], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45, check=False)
                    return (_r.stdout or _r.stderr or "KADO yanit vermedi").strip()[:3500]
                result = await loop.run_in_executor(None, _kado_center_call)

            elif name == "kado_influencer_content":
                import subprocess as _ksp
                def _kado_center_call():
                    _py = 'C:\\KADO\\KADO-AJANLAR\\.venv\\Scripts\\python.exe'
                    _center = 'C:\\KADO\\KADO-AJANLAR\\kado_ceo.py'
                    _r = _ksp.run([_py, _center, 'social-draft', str(args.get('project', "")), str(args.get('topic', ""))], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45, check=False)
                    return (_r.stdout or _r.stderr or "KADO yanit vermedi").strip()[:3500]
                result = await loop.run_in_executor(None, _kado_center_call)

            elif name == "kado_company_report":
                import subprocess as _ksp
                def _kado_center_call():
                    _py = 'C:\\KADO\\KADO-AJANLAR\\.venv\\Scripts\\python.exe'
                    _center = 'C:\\KADO\\KADO-AJANLAR\\kado_ceo.py'
                    _r = _ksp.run([_py, _center, 'report'], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45, check=False)
                    return (_r.stdout or _r.stderr or "KADO yanit vermedi").strip()[:3500]
                result = await loop.run_in_executor(None, _kado_center_call)

            # KADO_CLAUDE_12_BAGLANTI
            elif name == "computer_knowledge":
                import subprocess as _ksp

                def _computer_knowledge():
                    _r = _ksp.run(['C:\\KADO\\KADO-AJANLAR\\.venv\\Scripts\\python.exe', 'C:\\KADO\\KADO-AJANLAR\\kado_cekirdek.py', "ses", str(args.get("query", ""))],
                                  capture_output=True, text=True,
                                  encoding="utf-8", errors="replace",
                                  timeout=60, check=False)
                    return (_r.stdout or "").strip() or "Cevap alinamadi."

                result = await loop.run_in_executor(None, _computer_knowledge)

            elif name == "shell_run":


                r = await loop.run_in_executor(


                    None, lambda: shell_run(args.get("command", "")))


                result = r or "Komut çalıştırıldı."





            elif name == "toggle_webcam":


                action = str(args.get("action", "start")).strip().lower()


                if action == "start":


                    status = self._webcam_streamer.start()


                    if status == "ok":


                        self.ui.set_webcam_active(True)


                        result = (


                            "Webcam akışı başlatıldı. "


                            "Artık kameranı görüyorum — dilediğin zaman soru sorabilirsin."


                        )


                    elif status == "already_active":


                        result = "Webcam zaten açık, görüntü alıyorum."


                    else:


                        result = "Webcam başlatılamadı: opencv-python yüklü değil."


                else:


                    self._webcam_streamer.stop()


                    self.ui.set_webcam_active(False)


                    result = "Webcam akışı durduruldu."





            elif name == "play_media":


                r = await loop.run_in_executor(


                    None,


                    lambda: play_media(


                        args.get("query", ""),


                        args.get("provider", "auto"),


                        bool(args.get("autoplay", True)),


                    ),


                )


                result = r or "Medya oynatma başlatıldı."





            elif name == "control_media":


                r = await loop.run_in_executor(


                    None, lambda: control_media(args.get("action", "pause")))


                result = r or "Medya komutu gonderildi."





            elif name == "get_youtube_channel_report":


                r = await loop.run_in_executor(


                    None,


                    lambda: get_youtube_channel_report(


                        args.get("query", "overview"),


                        args.get("handle", ""),


                        int(args.get("video_limit", 6) or 6),


                    ),


                )


                result = r or "YouTube kanal raporu alindi."





            elif name == "computer_task":


                r = PC_AGENT.start(


                    args.get("goal", ""),


                    self._pc_notify,


                    self._pc_on_start,


                    self._pc_on_end,


                )


                result = r





            elif name == "computer_task_control":


                act = str(args.get("action", "status")).strip().lower()


                parts = []


                if act == "stop":


                    sing_mod.SING_STOP.set()


                    parts = [PC_AGENT.stop() if PC_AGENT.running else "", JOBS.stop()]


                elif act == "reply":


                    if PC_AGENT.running and PC_AGENT.question:


                        parts = [PC_AGENT.reply(args.get("answer", ""))]


                    else:


                        parts = [JOBS.reply(args.get("answer", ""))]


                else:


                    parts = [PC_AGENT.status() if PC_AGENT.running else "", JOBS.status()]


                result = " ".join(x for x in parts if x) or "Şu an çalışan bir görev ya da arka plan işi yok."





            elif name == "sing":


                if not self._el_on:


                    result = ("Şarkı söylemek için ElevenLabs sesi lazım (api_keys.json'da elevenlabs_api_key ve "


                              "elevenlabs_voice_id dolu olmalı).")


                else:


                    import threading as _th


                    _th.Thread(target=self._sing_worker, daemon=True,


                               args=(args.get("request", ""), args.get("style", ""), args.get("lyrics", ""))).start()


                    result = "Şarkı hazırlanıyor, birazdan başlıyor. SEN HİÇBİR ŞEY SÖYLEME, sessiz kal ve şarkıyı bırak."





            elif name == "message_me":


                result = await loop.run_in_executor(


                    None, lambda: phone_notify.send_whatsapp_self(args.get("text", "")))





            elif name == "quick_research":


                result = await loop.run_in_executor(None, lambda: quick_research(args.get("query", "")))





            elif name == "start_job":


                result = JOBS.start(args.get("goal", ""), self._pc_notify)





            elif name == "index_folder":


                import threading as _th


                _th.Thread(target=lambda: self._pc_notify(kado_brain.index_folder(args.get("path", ""))),


                           daemon=True).start()


                result = "Klasörü arka planda öğrenmeye başladım, bitince haber veririm."





            elif name == "search_my_files":


                result = await loop.run_in_executor(None, lambda: kado_brain.search_files(args.get("query", "")))





            elif name == "analyze_screen":


                r = await loop.run_in_executor(


                    None,


                    lambda: analyze_screen(


                        args.get("query", "Ekranda ne var?"),


                        args.get("target", "active_window"),


                    ),


                )


                result = r or "Ekran analizi tamamlandi."





            elif name == "send_whatsapp_message":


                r = await loop.run_in_executor(


                    None,


                    lambda: send_whatsapp_message(


                        args.get("message", ""),


                        args.get("phone_number", ""),


                        args.get("recipient_name", ""),


                        bool(args.get("send_now", False)),


                        args.get("app_target", "auto"),


                    ),


                )


                result = r or "WhatsApp işlemi tamamlandı."





            elif name == "save_whatsapp_contact":


                r = await loop.run_in_executor(


                    None,


                    lambda: save_whatsapp_contact(


                        args.get("display_name", ""),


                        args.get("phone_number", ""),


                        args.get("aliases", ""),


                    ),


                )


                result = r or "WhatsApp kişisi kaydedildi."





            else:


                result = f"Bilinmeyen araç: {name}"





        except Exception as e:


            result = f"Hata: {e}"


            had_exception = True


            traceback.print_exc()


            self.speak_error(name, e)





        tool_failed = self._result_looks_like_error(result)


        if tool_failed:


            if not had_exception:


                self.ui.set_state("ERROR")


        elif self._should_play_success_sfx(name, args, result):


            self.ui.play_success_sfx()





        if not tool_failed and not self.ui.muted:


            self.ui.set_state("LISTENING")





        print(f"[KADO] 📤 {name} → {str(result)[:80]}")


        return types.FunctionResponse(


            id=fc.id, name=name,


            response={"result": result}


        )





    async def _send_realtime(self):


        while True:


            msg = await self.out_queue.get()


            await self.session.send_realtime_input(media=msg)





    async def _stream_webcam_frames(self):


        """


        Webcam aktifken her 1.5s'de EN GÜNCEL kareyi session'a gönderir.


        Queue'suz 'latest frame' yaklaşımı: model hep şimdiki görüntüyü görür.


        """


        _last_sent: bytes | None = None


        while True:


            if not self._webcam_streamer.is_active:


                await asyncio.sleep(0.2)


                continue





            jpeg = self._webcam_streamer.get_latest_frame()


            if jpeg is None or jpeg is _last_sent:


                await asyncio.sleep(0.2)


                continue





            _last_sent = jpeg


            try:


                await self.session.send_realtime_input(


                    media={"data": jpeg, "mime_type": "image/jpeg"}


                )


            except Exception as e:


                print(f"[Webcam] Frame gönderilemedi: {e}")





            await asyncio.sleep(WEBCAM_SEND_INTERVAL)





    async def _update_ui_webcam_preview(self):


        """UI önizlemesini ~24 FPS günceller. AI akışından bağımsız."""


        frame_interval = 1.0 / 24.0   # ~0.0417 sn → 24 FPS


        while True:


            if self._webcam_streamer.is_active:


                jpeg = self._webcam_streamer.get_latest_frame()


                if jpeg:


                    self.ui.update_webcam_preview(jpeg)


            await asyncio.sleep(frame_interval)





    async def _listen_audio(self):


        print("[KADO] 🎤 Mikrofon başladı")


        stream = await asyncio.to_thread(


            pya.open,


            format=FORMAT, channels=CHANNELS,


            rate=SEND_SAMPLE_RATE, input=True,


            frames_per_buffer=CHUNK_SIZE,


        )


        try:


            while True:


                data = await asyncio.to_thread(


                    stream.read, CHUNK_SIZE, exception_on_overflow=False)


                with self._speaking_lock:


                    kado_speaking = self._is_speaking


                if not kado_speaking and not self.ui.muted and not self._paused:


                    await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})


        except Exception as e:


            print(f"[KADO] ❌ Mikrofon: {e}")


            raise


        finally:


            stream.close()





    async def _receive_audio(self):


        print("[KADO] 👂 Alım başladı")


        out_buf, in_buf = [], []


        output_noise = False


        output_noise_samples = []


        try:


            while True:


                async for response in self.session.receive():


                    if response.data and not self._el_on:


                        self.audio_in_queue.put_nowait(response.data)





                    if response.server_content:


                        sc = response.server_content





                        if sc.output_transcription and sc.output_transcription.text:


                            self.set_speaking(True)


                            raw_txt = sc.output_transcription.text.strip()


                            if raw_txt:


                                txt, had_noise = self._clean_transcript_text(raw_txt)


                                if had_noise:


                                    output_noise = True


                                    if len(output_noise_samples) < 4:


                                        output_noise_samples.append(raw_txt)


                                if txt:


                                    out_buf.append(txt)


                                    if self._el_on:


                                        self._el_pending += txt + " "


                                        self._el_flush()





                        if sc.input_transcription and sc.input_transcription.text:


                            txt = sc.input_transcription.text.strip()


                            if txt:


                                in_buf.append(txt)


                                self.ui.mark_user_activity(True)





                        if getattr(sc, "interrupted", False):


                            sing_mod.SING_STOP.set()


                        if getattr(sc, "interrupted", False) and self._el_on:


                            self._el_pending = ""


                            while self._el_queue is not None and not self._el_queue.empty():


                                self._el_queue.get_nowait()


                            while not self.audio_in_queue.empty():


                                self.audio_in_queue.get_nowait()





                        if sc.turn_complete:


                            if self._el_on:


                                self._el_flush(force=True)


                            else:


                                self.set_speaking(False)


                            self._el_refresh()


                            self._el_first = True





                            full_in = " ".join(in_buf).strip()


                            if full_in:


                                self.ui.write_log(f"Siz: {full_in}")


                            in_buf = []





                            full_out = " ".join(out_buf).strip()


                            if full_out:


                                self.ui.write_log(f"KADO: {full_out}")


                                if output_noise_samples:


                                    self.ui.write_debug(


                                        "Kısmen filtrelenen ses transcripti: " + " | ".join(output_noise_samples),


                                        level="WARN",


                                    )


                            elif output_noise:


                                self.ui.write_log("ERR: KADO sesli yanıtını çözümlerken bir hata oluştu.")


                                if output_noise_samples:


                                    self.ui.write_debug(


                                        "Filtrelenen ham transcript: " + " | ".join(output_noise_samples),


                                        level="WARN",


                                    )


                                self.ui.set_state("ERROR")


                            out_buf = []


                            output_noise = False


                            output_noise_samples = []





                    if response.tool_call:


                        fn_responses = []


                        for fc in response.tool_call.function_calls:


                            print(f"[KADO] 📞 {fc.name}")


                            fr = await self._execute_tool(fc)


                            fn_responses.append(fr)


                        await self.session.send_tool_response(


                            function_responses=fn_responses)





        except Exception as e:


            print(f"[KADO] ❌ Alım: {e}")


            traceback.print_exc()


            raise





    async def _play_audio(self):


        print("[KADO] 🔊 Ses çalma başladı")


        stream = await asyncio.to_thread(


            pya.open,


            format=FORMAT, channels=CHANNELS,


            rate=RECV_SAMPLE_RATE, output=True,


        )


        try:


            while True:


                if self._el_on:


                    try:


                        chunk = await asyncio.wait_for(self.audio_in_queue.get(), timeout=0.6)


                    except asyncio.TimeoutError:


                        if (self._el_played and not self._el_busy


                                and self._el_queue.empty()):


                            self.set_speaking(False)


                            self._el_played = False


                        continue


                    self._el_played = True


                else:


                    chunk = await self.audio_in_queue.get()


                self.set_speaking(True)


                await asyncio.to_thread(stream.write, chunk)


        except Exception as e:


            print(f"[KADO] ❌ Ses: {e}")


            raise


        finally:


            self.set_speaking(False)


            stream.close()





    async def run(self):


        connect_attempts = 0


        while True:


            # Duraklatılmışsa bağlanma, bekle


            if self._paused:


                await asyncio.sleep(1)


                continue





            try:


                # Client'ı her bağlanışta yeniden oluştur ve anahtarı tazeden oku.


                # Böylece yeni girilen API anahtarı anında geçerli olur; ilk


                # deneme başarısız olsa bile otomatik tekrar (3sn) kendini onarır.


                client = genai.Client(


                    api_key=get_api_key(),


                    http_options={"api_version": "v1alpha"}


                )


                print("[KADO] 🔌 Bağlanıyor...")


                self.ui.set_state("THINKING")


                config = self._build_config()





                async with (


                    client.aio.live.connect(


                        model=str(get_app_config_value("live_model", "") or LIVE_MODEL),


                        config=config) as session,


                    asyncio.TaskGroup() as tg,


                ):


                    self.session        = session


                    self._loop          = asyncio.get_event_loop()


                    self.audio_in_queue = asyncio.Queue()


                    self._el_queue      = asyncio.Queue()


                    self._el_pending    = ""


                    self._el_refresh()


                    self.out_queue      = asyncio.Queue(maxsize=10)





                    print("[KADO] ✅ Bağlandı.")


                    connect_attempts = 0          # başarılı bağlantı → sayaç sıfırla


                    self.ui.set_state("LISTENING")


                    self.ui.write_log("SYS: KADO hazır. Dinliyorum...")





                    tg.create_task(self._send_realtime())


                    tg.create_task(self._listen_audio())


                    tg.create_task(self._receive_audio())


                    tg.create_task(self._play_audio())


                    tg.create_task(self._elevenlabs_worker())


                    tg.create_task(self._agent_meeting_notifier())


                    tg.create_task(self._content_pack_notifier())


                    tg.create_task(self._stream_webcam_frames())


                    tg.create_task(self._update_ui_webcam_preview())





            except Exception as e:


                print(f"[KADO] ⚠️ {e}")


                traceback.print_exc()


                self.set_speaking(False)


                # Webcam akışını durdur — yeni session'da yeniden başlayacak


                if self._webcam_streamer.is_active:


                    self._webcam_streamer.stop()


                    self.ui.set_webcam_active(False)





                connect_attempts += 1


                # İlk birkaç deneme sessiz: yeni girilen API anahtarı Google


                # tarafında saniyeler içinde aktifleşebilir. Kullanıcıya hemen


                # "hatalı anahtar" göstermeyip kısa aralıkla otomatik tekrar dene.


                if connect_attempts <= 3:


                    self.ui.set_state("INITIALISING")


                    print(f"[KADO] 🔄 Bağlanmayı tekrar deniyor ({connect_attempts}/3)...")


                    await asyncio.sleep(2)


                else:


                    self.ui.write_log(


                        f"ERR: KADO baglanamiyor — API anahtarini ve internet "


                        f"baglantisini kontrol et. ({e})"


                    )


                    self.ui.set_state("ERROR")


                    print("[KADO] 🔄 5 saniyede yeniden bağlanıyor...")


                    await asyncio.sleep(5)








def run_selftest() -> int:


    """


    Kurulum tanisi: `KADO.exe --selftest`





    Arayuzu acmadan yollari, kritik modulleri ve temel araclari dener.


    Destek isterken kullaniciya "bunu calistirip ciktiyi gonder" demek icin.


    """


    import app_paths





    # Penceresiz .exe'de konsol yoktur → ciktiyi dosyaya da yaz.


    lines: list[str] = []





    def out(text=""):


        lines.append(str(text))


        print(text)





    out("K.A.D.O — kurulum tanisi\n")


    out(app_paths.describe())





    ok = bad = 0





    def check(label, fn):


        nonlocal ok, bad


        try:


            detail = fn()


            out(f"  [OK]   {label}" + (f" — {detail}" if detail else ""))


            ok += 1


        except Exception as exc:


            out(f"  [HATA] {label} — {type(exc).__name__}: {exc}")


            bad += 1





    out("\nKritik moduller:")


    for mod in ("win32com.client", "pythoncom", "win32gui", "cv2",


                "pyaudio", "mss", "psutil", "PIL.Image", "google.genai"):


        check(mod, lambda m=mod: __import__(m) and "")





    out("\nGomulu kaynaklar:")


    for rel in (("core", "prompt.txt"), ("Fonts", "Grift-Regular.ttf"), ("SFX", "HUD.mp3")):


        check("/".join(rel), lambda r=rel: "bulundu" if app_paths.resource_path(*r).exists()


              else (_ for _ in ()).throw(FileNotFoundError(app_paths.resource_path(*r))))





    out("\nYazma izni:")





    def _write_probe():


        p = app_paths.data_path("config", ".probe")


        p.write_text("ok", encoding="utf-8")


        p.unlink()


        return str(p.parent)





    check("veri klasorune yazilabiliyor", _write_probe)





    out("\nAyarlar:")


    check("API anahtari girilmis mi",


          lambda: "evet" if get_app_config_value("gemini_api_key", "") else "HAYIR (uygulamadan gir)")





    out("\nAraclar:")


    check("sys_info", lambda: sys_info("battery"))


    check("takvim", lambda: get_calendar_events("today"))


    check("PowerShell", lambda: shell_run("Write-Output tamam"))


    check("COM (kisayol/Outlook icin)", lambda: _com_probe())





    out(f"\nSONUC: {ok} basarili, {bad} hatali")





    try:


        log = app_paths.data_path("kado_tani.log")


        log.write_text("\n".join(lines), encoding="utf-8")


        print(f"\nRapor kaydedildi: {log}")


    except Exception:


        pass





    return 1 if bad else 0








def _com_probe() -> str:


    from actions.platform_utils import com_context





    with com_context():


        import win32com.client





        shell = win32com.client.Dispatch("WScript.Shell")


        return "WScript.Shell olusturuldu"








def _dispatch_web_modes():


    """


    Telefon/web modlari. .exe icinde "python server.py" calistirilamadigi icin


    KADO.exe kendini bu bayraklarla yeniden cagirir.


    """


    argv = sys.argv[1:]





    if "--web" in argv:


        # Penceresiz .exe'nin ciktisi hicbir yere gitmiyordu; TELEFON.bat'in


        # konsoluna baglan ki adres ve QR kodu gorunsun.


        attach_parent_console()


        from kado_web.launcher import run_orchestrator





        raise SystemExit(run_orchestrator())





    if "--web-server" in argv:


        # server.py kendi argparse'ini kullaniyor — kendi bayragimizi cikar


        sys.argv = [sys.argv[0]] + [a for a in argv if a != "--web-server"]


        from kado_web.server import main as server_main





        raise SystemExit(server_main() or 0)





    if "--web-agent" in argv:


        sys.argv = [sys.argv[0]] + [a for a in argv if a != "--web-agent"]


        from kado_web.agent import main as agent_main





        try:


            asyncio.run(agent_main())


        except KeyboardInterrupt:


            pass


        raise SystemExit(0)








def main():


    if "--selftest" in sys.argv:


        raise SystemExit(run_selftest())





    _dispatch_web_modes()





    if os.environ.get("TERM_PROGRAM") == "vscode":


        print("[KADO] VS Code icinden baslatildi.")





    # Zaten calisan bir KADO varsa yenisini acma, mevcut pencereyi one getir.


    if not acquire_single_instance():


        print("[KADO] Zaten calisiyor — mevcut pencere one getiriliyor.")


        focus_window("K.A.D.O")


        return





    ui = KadoUI()





    def runner():


        ui.wait_for_api_key()


        kado = KadoLive(ui)


        try:


            asyncio.run(kado.run())


        except KeyboardInterrupt:


            print("\n🔴 Kapatılıyor...")





    threading.Thread(target=runner, daemon=True).start()


    ui.root.mainloop()








if __name__ == "__main__":


    main()


