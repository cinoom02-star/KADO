@echo off
chcp 65001 >nul
title KADO — Telefon icin guvenlik duvari izni

:: ============================================================
::  NE ISE YARAR
::  Telefon ayni Wi-Fi uzerinden KADO'e baglanirken Windows
::  Guvenlik Duvari gelen baglantiyi engelleyebilir. Bu dosya
::  SADECE 8765-8766 portlarina gelen baglantiya izin verir.
::
::  NE ZAMAN GEREKIR
::  Panelde "guvenlik duvari sorarsa IZIN VER" yaziyorsa ve
::  telefon QR'i okuttugunda sayfa ACILMIYORSA.
::
::  Yonetici izni ister (UAC penceresi cikar) — kural eklemek
::  Windows'ta yonetici yetkisi gerektirir.
:: ============================================================

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Yonetici izni isteniyor...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo.
echo ============================================================
echo   KADO — Telefon baglantisi icin guvenlik duvari izni
echo ============================================================
echo.

netsh advfirewall firewall delete rule name="KADO Telefon" >nul 2>&1
netsh advfirewall firewall add rule name="KADO Telefon" dir=in action=allow protocol=TCP localport=8765-8766 profile=any

if %errorlevel% equ 0 (
    echo.
    echo   [TAMAM] Izin verildi.
    echo   Simdi KADO'te TELEFON panelini yeniden baslat ve QR'i okut.
) else (
    echo.
    echo   [HATA] Kural eklenemedi.
    echo   Windows Guvenlik Duvari ayarlarindan KADO'e elle izin ver.
)

echo.
echo   Izni geri almak icin:
echo     netsh advfirewall firewall delete rule name="KADO Telefon"
echo.
pause
