# -*- coding: utf-8 -*-
"""KADO bildirim yamasi: onay bekleyen yeni paket olunca KADO sesli haber verir.
Yedek alir, ankraji tek eslesmeyle arar, derler, bozulursa geri koyar.
Kullanim: python kado_bildirim_yama.py [sistem_klasoru] [--geri]
"""
import sys, shutil, py_compile, datetime
from pathlib import Path

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
SIS = Path(ARGS[0]) if ARGS else Path(r"C:\KADO\kado\sistem")
YEDEK = Path(r"C:\KADO\KADO-AJANLAR\yedekler")
PYEXE = r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe"
ONAY = r"C:\KADO\KADO-AJANLAR\kado_onay.py"
MARK = "_content_pack_notifier"

METHOD_ANCHOR = "    def _pc_notify(self, text: str):"
CALL_ANCHOR = "                    tg.create_task(self._agent_meeting_notifier())\n"

METHOD_NEW = '''    async def _content_pack_notifier(self):
        """Onay bekleyen yeni icerik paketlerini sesli haber verir."""
        import subprocess
        import json
        import time
        from pathlib import Path

        root = Path(r"C:\\KADO\\KADO-AJANLAR")
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
            r = subprocess.run([r"%(py)s", r"%(onay)s", "listele"],
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

''' % {"py": PYEXE, "onay": ONAY}

CALL_NEW = "                    tg.create_task(self._content_pack_notifier())\n"


def main():
    if "--geri" in sys.argv:
        b = sorted(YEDEK.glob("main.py.bildirim_*"))
        if not b:
            print("YEDEK YOK"); return
        shutil.copy2(b[-1], SIS / "main.py"); print("GERI KONDU:", b[-1].name); return
    mp = SIS / "main.py"
    if not mp.is_file():
        print("HATA: main.py bulunamadi:", SIS); return
    raw = mp.read_bytes()
    crlf = b"\\r\\n" in raw or b"\r\n" in raw
    txt = raw.decode("utf-8").replace("\r\n", "\n")
    if MARK in txt:
        print("DURUM: ZATEN YAMALI, yedek alinmadi."); return
    if txt.count(METHOD_ANCHOR) != 1 or txt.count(CALL_ANCHOR) != 1:
        print("HATA: ankraj sayisi beklenen degil (metod=%d, cagri=%d). Degismedi." %
              (txt.count(METHOD_ANCHOR), txt.count(CALL_ANCHOR)))
        return
    YEDEK.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bk = YEDEK / ("main.py.bildirim_" + ts)
    shutil.copy2(mp, bk)
    print("YEDEK ALINDI:", bk.name)
    new = txt.replace(METHOD_ANCHOR, METHOD_NEW + METHOD_ANCHOR)
    new = new.replace(CALL_ANCHOR, CALL_ANCHOR + CALL_NEW)
    if crlf:
        new = new.replace("\n", "\r\n")
    mp.write_bytes(new.encode("utf-8"))
    try:
        py_compile.compile(str(mp), doraise=True, cfile=str(YEDEK / "_derle_main.pyc"))
        print("DURUM: YAMA TAMAM. KADO'yu kapatip yeniden ac.")
    except Exception as e:
        print("HATA:", e, "-> geri aliniyor")
        shutil.copy2(bk, mp)
        print("DURUM: ESKI HALE DONULDU")


main()
