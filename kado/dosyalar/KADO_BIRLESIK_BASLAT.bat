@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sistem\kado_call\baslat-birlesik.ps1"
pause
