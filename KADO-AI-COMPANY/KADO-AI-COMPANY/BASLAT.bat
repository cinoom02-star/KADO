@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows.ps1" -Action Start
set "KADO_EXIT=%ERRORLEVEL%"
if not "%KADO_EXIT%"=="0" echo Baslatma basarisiz. data\logs klasorunu inceleyin.
pause
exit /b %KADO_EXIT%
