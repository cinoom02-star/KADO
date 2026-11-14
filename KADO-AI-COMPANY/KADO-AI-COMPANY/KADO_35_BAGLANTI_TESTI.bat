@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\kado_company_launcher.ps1" -CheckOnly
set "KADO_EXIT=%ERRORLEVEL%"
pause
exit /b %KADO_EXIT%
