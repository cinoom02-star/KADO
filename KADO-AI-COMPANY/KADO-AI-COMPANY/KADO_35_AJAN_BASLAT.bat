@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\kado_company_launcher.ps1"
set "KADO_EXIT=%ERRORLEVEL%"
if not "%KADO_EXIT%"=="0" echo Baglanti baslatilamadi. Yukaridaki hata metnini kontrol edin.
pause
exit /b %KADO_EXIT%
