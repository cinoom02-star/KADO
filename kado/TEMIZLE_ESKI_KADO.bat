@echo off
chcp 65001 >nul
title KADO — Eski kurulumlari ve engelleri temizle

:: ============================================================
::  NE ISE YARAR
::  Ayni bilgisayarda birden fazla KADO denendiyse geride
::  su kalintilar kalir ve YENI surumu de bozar:
::
::   1. Arka planda calisan eski KADO — 8765/8766 portlarini
::      tutar, yeni surum o portlari acamaz.
::   2. Guvenlik duvari uyarisinda bir kez "Iptal" dendiyse
::      Windows o dosya icin kalici bir ENGELLEME kurali yazar
::      ve bir daha SORMAZ. Telefon sessizce baglanamaz.
::
::  Bu dosya ikisini de temizler. KADO'i SILMEZ, sadece
::  calisan surecleri kapatir ve guvenlik duvari kurallarini
::  sifirlar.
:: ============================================================

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Yonetici izni isteniyor...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo.
echo ============================================================
echo   KADO — Eski kalintilari temizleme
echo ============================================================
echo.

echo [1/3] Calisan KADO surecleri kapatiliyor...
taskkill /IM KADO.exe /T /F >nul 2>&1
taskkill /IM kado.exe /T /F >nul 2>&1
taskkill /IM cloudflared.exe /T /F >nul 2>&1
echo       tamam
echo.

echo [2/3] Eski guvenlik duvari kurallari siliniyor...
for %%N in ("kado" "KADO" "KADO.exe" "kado.exe" "KADO Telefon") do (
    netsh advfirewall firewall delete rule name=%%N >nul 2>&1
)
echo       tamam
echo.

echo [3/3] Yeni izin ekleniyor (8765-8766)...
netsh advfirewall firewall add rule name="KADO Telefon" dir=in action=allow protocol=TCP localport=8765-8766 profile=any >nul 2>&1

if %errorlevel% equ 0 (
    echo       tamam
) else (
    echo       EKLENEMEDI - elle izin vermen gerekebilir
)

echo.
echo ============================================================
echo   BITTI
echo ============================================================
echo.
echo   SIMDI SIRASIYLA:
echo     1. Eski KADO klasorlerini/dosyalarini SIL
echo        (ozellikle masaustundeki tek basina kado.exe)
echo     2. Yeni "KADO V3.2" zip'ini C:\KADO gibi
echo        BASIT bir klasore cikar (OneDrive icine DEGIL)
echo     3. Oradaki KADO.exe'yi calistir
echo     4. TELEFON panelinde surumun v3.2 yazdigini dogrula
echo.
pause
