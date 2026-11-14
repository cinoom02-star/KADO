# -*- mode: python ; coding: utf-8 -*-
"""
KADO — PyInstaller yapilandirmasi (Windows)

Kullanim (build_exe.ps1 bunu cagirir):
    pyinstaller kado.spec --noconfirm

Ortam degiskenleri:
    KADO_CONSOLE=1   → konsol penceresiyle derle (hata ayiklama icin)
    KADO_ONEFILE=1   → tek dosya .exe (yavas acilir, onerilmez)
"""

import os
from pathlib import Path

PROJECT = Path(SPECPATH).resolve()

CONSOLE = os.environ.get("KADO_CONSOLE") == "1"
ONEFILE = os.environ.get("KADO_ONEFILE") == "1"

# ── Pakete gomulecek salt-okunur kaynaklar ──────────────────────────────────
# Yazilabilir dosyalar (api_keys.json, memory/*) BILEREK dahil edilmez;
# app_paths.data_path() onlari exe'nin yanina yazar.
datas = [
    (str(PROJECT / "core" / "prompt.txt"), "core"),
]
for pattern, dest in ((("Fonts", "*.ttf"), "Fonts"),
                      (("SFX", "*.mp3"), "SFX"),
                      (("Icon", "*.png"), "Icon"),
                      (("kado_web/static", "*"), "kado_web/static")):
    folder, glob = pattern
    for f in sorted((PROJECT / folder).glob(glob)):
        if f.is_file():
            datas.append((str(f), dest))

# cloudflared — telefondan INTERNET uzerinden baglanmak icin (opsiyonel ozellik).
# Apache-2.0 lisansli, Cloudflare Inc. tarafindan imzali. Lisans metni de
# pakete konur (Apache-2.0 atif sarti).
_cf = PROJECT / "cloudflared.exe"
if _cf.exists():
    datas.append((str(_cf), "."))
_cf_license = PROJECT / "CLOUDFLARED_LICENSE.txt"
if _cf_license.exists():
    datas.append((str(_cf_license), "."))

# ── pywin32 ve digerleri statik analizle bulunamayabiliyor ──────────────────
hiddenimports = [
    "win32com", "win32com.client", "pythoncom", "pywintypes", "win32timezone",
    "win32api", "win32con", "win32gui", "win32process", "win32clipboard",
    "mss", "mss.windows",
    "psutil",
    "google.genai",
    # Telefon/web modu — bu moduller fonksiyon icinde lazy import edildigi
    # icin statik analiz bulamiyor
    "kado_web", "kado_web.server", "kado_web.agent", "kado_web.launcher",
    "qrcode",
    "websockets", "websockets.legacy", "websockets.legacy.client",
    "fastapi", "starlette",
    # uvicorn calisma aninda dinamik import ediyor
    "uvicorn", "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
    "uvicorn.loops.asyncio", "uvicorn.protocols", "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto", "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan", "uvicorn.lifespan.on", "uvicorn.lifespan.off",
]

# Uygulamanin ihtiyaci olmayan agir bagimliliklari disarida birak
excludes = [
    "tkinter.test", "test", "unittest",
    "matplotlib", "scipy", "pandas", "IPython", "notebook",
    "pytest", "setuptools", "pip",
]

icon_file = PROJECT / "Icon" / "KADO.ico"

a = Analysis(
    [str(PROJECT / "main.py")],
    pathex=[str(PROJECT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

if ONEFILE:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name="KADO",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        runtime_tmpdir=None,
        console=CONSOLE,
        disable_windowed_traceback=False,
        icon=str(icon_file) if icon_file.exists() else None,
    )
else:
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="KADO",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=CONSOLE,
        disable_windowed_traceback=False,
        icon=str(icon_file) if icon_file.exists() else None,
    )
    coll = COLLECT(
        exe, a.binaries, a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name="KADO",
    )
