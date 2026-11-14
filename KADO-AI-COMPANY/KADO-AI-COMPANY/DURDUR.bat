@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows.ps1" -Action Stop
set "KADO_EXIT=%ERRORLEVEL%"
pause
exit /b %KADO_EXIT%
