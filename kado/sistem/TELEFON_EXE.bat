@echo off
chcp 65001 >nul
title K.A.D.O - TELEFONDAN BAGLAN
rem ╔══════════════════════════════════════════════════════════╗
rem ║   K.A.D.O — TELEFONDAN BAGLAN (EXE surumu)            ║
rem ║   Cift tikla → telefon icin adres + QR kod cikar.         ║
rem ╚══════════════════════════════════════════════════════════╝
rem
rem KADO.exe kendi icinde sunucuyu ve ajani baslatir; Python gerekmez.

if not exist "%~dp0KADO.exe" (
    echo.
    echo KADO.exe bulunamadi. Bu dosya KADO.exe ile ayni klasorde olmali.
    echo.
    pause
    exit /b 1
)

"%~dp0KADO.exe" --web

echo.
echo KADO Web durdu.
pause
