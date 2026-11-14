@echo off
setlocal
if "%~2"=="" (
  echo Kullanim: KADO_GERI_YUKLE.bat "YEDEK.zip" "YENI_KLASOR"
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0scripts\recovery_cli.py" restore "%~f1" "%~f2"
exit /b %ERRORLEVEL%
