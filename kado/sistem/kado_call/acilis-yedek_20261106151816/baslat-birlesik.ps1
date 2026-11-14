$ErrorActionPreference = 'Stop'
$appRoot = Split-Path -Parent $PSScriptRoot
$kadoRoot = Split-Path -Parent $appRoot
try {
    $pythonExe = Join-Path $appRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path $pythonExe)) { throw 'Mevcut Kado Python ortami bulunamadi. Once normal BASLAT.bat ile kurulumu tamamlayin.' }
    $script = Join-Path $appRoot 'kado_birlesik.py'
    Write-Host 'Normal Kado zaten aciksa once kapatin. Asil Kado ve WhatsApp birlikte baslatiliyor.'
    $logTag = Get-Date -Format 'yyyyMMdd_HHmmss'
    $outLog = Join-Path $PSScriptRoot ('kado_' + $logTag + '.log')
    $errorLog = Join-Path $PSScriptRoot ('hata_' + $logTag + '.log')
    $kadoProcess = Start-Process -FilePath $pythonExe -ArgumentList @('-u', ('"' + $script + '"')) -WorkingDirectory $appRoot -RedirectStandardOutput $outLog -RedirectStandardError $errorLog -PassThru
    $ready = $false
    for ($attempt=0; $attempt -lt 120; $attempt++) {
        Start-Sleep -Milliseconds 500
        $kadoProcess.Refresh()
        if ($kadoProcess.HasExited) {
            if (Test-Path $errorLog) { Get-Content $errorLog -Tail 18 | Write-Host }
            throw ('Kado acilamadi veya eski Kado zaten acik. Hata dosyasi: ' + $errorLog)
        }
        $statePath = Join-Path $PSScriptRoot 'link.json'
        if (Test-Path $statePath) {
            try {
                $state = Get-Content $statePath -Raw | ConvertFrom-Json
                if ($state.ready -and (Get-Process -Id $state.pid -ErrorAction SilentlyContinue)) { $ready = $true; break }
            } catch { }
        }
    }
    if (-not $ready) { throw 'Kado baglantisi hazir olmadi. Kado penceresindeki hata satirini kontrol edin.' }
    & (Join-Path $kadoRoot 'WHATSAPP_BASLAT.bat')
} catch { Write-Host $_.Exception.Message -ForegroundColor Red; exit 1 }
