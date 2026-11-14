@echo off
setlocal
pushd "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Once KURULUM.bat calistirin.
  popd
  exit /b 1
)
".venv\Scripts\python.exe" scripts\recovery_cli.py
set "KADO_EXIT=%ERRORLEVEL%"
popd
pause
exit /b %KADO_EXIT%
