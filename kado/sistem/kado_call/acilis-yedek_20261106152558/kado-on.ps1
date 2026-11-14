$ErrorActionPreference = 'Stop'
$appRoot = Split-Path -Parent $PSScriptRoot
Set-Location $appRoot
$pythonExe = Join-Path $appRoot '.venv\Scripts\python.exe'
try {
    & $pythonExe -u (Join-Path $appRoot 'kado_birlesik.py')
    Write-Host ('Kado kapandi. Sonuc kodu: ' + $LASTEXITCODE)
} catch { Write-Host $_.Exception.Message -ForegroundColor Red }
