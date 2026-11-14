# -*- coding: utf-8 -*-
"""KADO sesli komut yamasi: start_content_task + get_content_status.
Yedek alir, her ankraji tek eslesmeyle arar, derler, bozulursa geri koyar.
Kullanim: python kado_ses_yama.py [sistem_klasoru] [--geri]
"""
import sys, shutil, py_compile, datetime
from pathlib import Path

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
SIS = Path(ARGS[0]) if ARGS else Path(r"C:\KADO\kado\sistem")
YEDEK = Path(r"C:\KADO\KADO-AJANLAR\yedekler")
BRIDGE = r"C:\KADO\KADO-AJANLAR\kado_ses_icerik_koprusu.py"
PYEXE = r"C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe"
MARK = "start_content_task"

TOOL_ANCHOR = '    {\n        "name": "open_app",'
TOOL_NEW = '''    {
        "name": "start_content_task",
        "description": (
            "Kullanici bir proje icin gonderi, gorsel kart ve video "
            "hazirlanmasini istediginde kullan. Ornek: 'Han Toys icin "
            "icerik hazirla'. Sadece kayitli projeler calisir. "
            "Hicbir sey yayinlanmaz, sonuc onay bekler. Bittigini "
            "iddia etme; baslatma istegi gonderilir."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "project": {
                    "type": "STRING",
                    "description": "Proje adi (ornek: Han Toys, KADO)"
                },
                "again": {
                    "type": "BOOLEAN",
                    "description": "Bugun zaten uretildiyse yeniden uret"
                }
            },
            "required": ["project"]
        }
    },

    {
        "name": "get_content_status",
        "description": (
            "Kullanici icerik hattinin durumunu, onay bekleyen "
            "paketleri veya bugun ne uretildigini sordugunda kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },

'''

MAIN_ANCHOR = '            elif name == "shell_run":'
MAIN_NEW = '''            elif name == "start_content_task":
                import subprocess as _csp

                def _content_task():
                    _cmd = [r"%(py)s", r"%(br)s", "baslat",
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
                    _r = _csp2.run([r"%(py)s", r"%(br)s", "durum"],
                                   capture_output=True, text=True,
                                   encoding="utf-8", errors="replace",
                                   timeout=40, check=False)
                    return (_r.stdout or "").strip() or "Durum okunamadi."

                result = await loop.run_in_executor(None, _content_status)

''' % {"py": PYEXE, "br": BRIDGE}


def patch(path, anchor, new):
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    txt = raw.decode("utf-8").replace("\r\n", "\n")
    if MARK in txt:
        print("ZATEN YAMALI:", path.name)
        return None
    if txt.count(anchor) != 1:
        raise RuntimeError("%s: ankraj %d kez bulundu (1 olmali)" % (path.name, txt.count(anchor)))
    txt = txt.replace(anchor, new + anchor)
    if crlf:
        txt = txt.replace("\n", "\r\n")
    path.write_bytes(txt.encode("utf-8"))
    return True


def geri():
    for n in ("main.py", "tool_defs.py"):
        b = sorted(YEDEK.glob(n + ".ses_yama_*"))
        if not b:
            print("YEDEK YOK:", n); continue
        shutil.copy2(b[-1], SIS / n); print("GERI KONDU:", n, "<-", b[-1].name)


def main():
    if "--geri" in sys.argv:
        return geri()
    mp, tp = SIS / "main.py", SIS / "tool_defs.py"
    if not (mp.is_file() and tp.is_file()):
        print("HATA: main.py/tool_defs.py bulunamadi:", SIS); return
    if MARK in mp.read_text(encoding="utf-8") and MARK in tp.read_text(encoding="utf-8"):
        print("DURUM: ZATEN YAMALI, yedek alinmadi."); return
    YEDEK.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    for p in (mp, tp):
        shutil.copy2(p, YEDEK / (p.name + ".ses_yama_" + ts))
    print("YEDEK ALINDI:", ts)
    try:
        a = patch(tp, TOOL_ANCHOR, TOOL_NEW)
        b = patch(mp, MAIN_ANCHOR, MAIN_NEW)
        for p in (tp, mp):
            py_compile.compile(str(p), doraise=True, cfile=str(YEDEK / ("_derle_" + p.name + "c")))
        if a is None and b is None:
            print("DURUM: ZATEN YAMALIYDI")
        else:
            print("DURUM: YAMA TAMAM. KADO'yu kapatip yeniden ac.")
    except Exception as e:
        print("HATA:", e, "-> geri aliniyor")
        for p in (mp, tp):
            shutil.copy2(YEDEK / (p.name + ".ses_yama_" + ts), p)
        print("DURUM: ESKI HALE DONULDU")


main()
