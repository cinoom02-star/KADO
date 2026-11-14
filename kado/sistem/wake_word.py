"""
Wake-word dinleyicisi — "Kado" kelimesini duyunca tetiklenir.
Bulut tabanli konusma tanima kullanir (internet baglantisi gerekir).
Tamamen yerel calistirmak icin farkli bir motorla degistirilebilir.
"""

import threading
import speech_recognition as sr

WAKE_WORD = "kado"
# Konuşma tanıma bazen farklı yazar; bunların hepsi "kado" sayılır
WAKE_VARIANTS = ("kado", "kaddo", "kadu", "kato", "cado", "kadoo")


class WakeWordListener:
    """
    Arka planda sürekli mikrofonu dinler.
    Wake-word duyulunca, sonrasındaki konuşmayı yakalar
    ve on_wake(text) callback'ini çağırır.
    """

    def __init__(self, on_wake, ui):
        self.on_wake   = on_wake
        self.ui        = ui
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold    = 300
        self.recognizer.dynamic_energy_threshold = True
        self._thread   = None
        self._running  = False

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[WakeWord] 🎤 Dinleniyor... 'Kado' diyerek başlatın.")

    def stop(self):
        self._running = False

    def _loop(self):
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            while self._running:
                if self.ui.muted:
                    import time; time.sleep(0.2)
                    continue
                try:
                    # Kısa bir ses parçası al (wake-word tespiti için)
                    audio = self.recognizer.listen(source, timeout=5,
                                                   phrase_time_limit=4)
                    text = self.recognizer.recognize_google(audio,
                                                            language="tr-TR").lower()
                    print(f"[WakeWord] Duyuldu: {text}")

                    hit = next((w for w in WAKE_VARIANTS if w in text), None)
                    if hit:
                        # Wake-word sonrasındaki kısım varsa onu al
                        after = text.split(hit, 1)[-1].strip()
                        if len(after) > 3:
                            # "Kado müzik aç" → "müzik aç"
                            self.on_wake(after)
                        else:
                            # Sadece "Kado" dediyse → daha fazla komut bekle
                            self.ui.write_log("SYS: Evet efendim?")
                            self.ui.set_state("LISTENING")
                            try:
                                audio2 = self.recognizer.listen(source,
                                                                timeout=6,
                                                                phrase_time_limit=8)
                                cmd = self.recognizer.recognize_google(
                                    audio2, language="tr-TR")
                                if cmd.strip():
                                    self.on_wake(cmd.strip())
                            except (sr.WaitTimeoutError, sr.UnknownValueError):
                                pass

                except sr.WaitTimeoutError:
                    pass
                except sr.UnknownValueError:
                    pass
                except Exception as e:
                    print(f"[WakeWord] Hata: {e}")
