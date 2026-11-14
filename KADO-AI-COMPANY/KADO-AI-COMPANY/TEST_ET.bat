@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows.ps1" -Action Test
set "KADO_EXIT=%ERRORLEVEL%"
if not "%KADO_EXIT%"=="0" echo Test veya derleme basarisiz; sonuc basarili olarak kabul edilmedi.
pause
exit /b %KADO_EXIT%
