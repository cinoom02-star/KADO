$ErrorActionPreference = 'Stop'
$appRoot = Split-Path -Parent $PSScriptRoot
$kadoRoot = Split-Path -Parent $appRoot
try {
    if (-not (Test-Path (Join-Path $appRoot '.venv\Scripts\python.exe'))) { throw 'Mevcut Kado Python ortami bulunamadi.' }
    $foreground = Join-Path $PSScriptRoot 'kado-on.ps1'
    $powershellExe = (Get-Command powershell.exe).Source
    Write-Host 'Asil Kado aciliyor. Yeni PowerShell penceresini acik birakin.'
    Start-Process -FilePath $powershellExe -ArgumentList @('-NoExit','-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$foreground+'"')) | Out-Null
    $ready = $false
    for ($attempt=0; $attempt -lt 120; $attempt++) {
        Start-Sleep -Milliseconds 500
        try {
            $state = Get-Content (Join-Path $PSScriptRoot 'link.json') -Raw | ConvertFrom-Json
            if (-not $state.ready) { continue }
            $request = [System.Net.HttpWebRequest]::Create('http://127.0.0.1:' + $state.port + '/health')
            $request.Proxy = $null
            $request.Timeout = 1500
            $request.Headers['Authorization'] = 'Bearer ' + $state.token
            $response = $request.GetResponse()
            try {
                $reader = New-Object System.IO.StreamReader($response.GetResponseStream())
                try { $health = $reader.ReadToEnd() | ConvertFrom-Json } finally { $reader.Dispose() }
                if ($health.ready) { $ready=$true; break }
            } finally { $response.Dispose() }
        } catch { }
    }
    if (-not $ready) { throw 'Canli Kado baglantisi hazir olmadi. Yeni acilan Kado PowerShell penceresindeki hatayi kontrol edin.' }
    Write-Host 'Asil Kado canli baglantisi dogrulandi. WhatsApp mesaji aciliyor.' -ForegroundColor Green
    & (Join-Path $kadoRoot 'WHATSAPP_BASLAT.bat')
} catch { Write-Host $_.Exception.Message -ForegroundColor Red; exit 1 }
