@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows.ps1" -Action Install
set "KADO_EXIT=%ERRORLEVEL%"
if not "%KADO_EXIT%"=="0" echo Kurulum basarisiz. Yukaridaki hata aciklamasini inceleyin.
pause
exit /b %KADO_EXIT%
