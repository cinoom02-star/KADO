@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sistem\kado_call\arama-kur.ps1"
pause
