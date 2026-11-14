@echo off
chcp 65001 >nul
title K.A.D.O
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0BASLAT.ps1"
if errorlevel 1 (
    echo.
    echo KADO beklenmedik sekilde kapandi.
    pause
)
