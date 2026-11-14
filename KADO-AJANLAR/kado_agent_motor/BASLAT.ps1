$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = 'C:\KADO\KADO-AJANLAR\.venv\Scripts\python.exe'
if (!(Test-Path $python)) { $python = 'python' }
& $python (Join-Path $PSScriptRoot 'kado_motor.py') calis
