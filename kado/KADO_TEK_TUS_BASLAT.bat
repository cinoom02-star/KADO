@echo off
chcp 65001 >nul
title KADO TEK TUS BASLAT
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0KADO_TEK_TUS_BASLAT.ps1"
if errorlevel 1 (
    echo KADO baslatma hatasi.
    pause
)
