$ErrorActionPreference = 'Stop'
$bridgeDir = $PSScriptRoot
$appDir = Split-Path -Parent $bridgeDir
Set-Location $bridgeDir
try {
    $nodeCmd = Get-Command node -ErrorAction SilentlyContinue
    if (-not $nodeCmd) {
        $nodeCandidate = Join-Path $env:ProgramFiles 'nodejs\node.exe'
        if (Test-Path $nodeCandidate) { $env:Path = (Split-Path $nodeCandidate) + ';' + $env:Path }
        $nodeCmd = Get-Command node -ErrorAction SilentlyContinue
    }
    if (-not $nodeCmd) { throw 'Node.js 22 veya uzeri LTS kurulmali. Node.js kurduktan sonra yeniden acin.' }
    $nodeMajor = [int](((& node --version).Trim().TrimStart('v')).Split('.')[0])
    if ($nodeMajor -lt 22) { throw 'Node.js 22 veya uzeri gerekli.' }
    $pyCandidate = Join-Path $appDir '.venv\Scripts\python.exe'
    if (Test-Path $pyCandidate) { $env:KADO_PY = $pyCandidate }
    else {
        $pyCmd = Get-Command python -ErrorAction SilentlyContinue
        if ($pyCmd) { $env:KADO_PY = $pyCmd.Source }
        else {
            $found = & py -3 -c 'import sys; print(sys.executable)'
            if ($LASTEXITCODE -ne 0) { throw 'Python bulunamadi. Once normal Kado BASLAT.bat dosyasini calistirin.' }
            $env:KADO_PY = $found.Trim()
        }
    }
    if (-not (Test-Path (Join-Path $appDir 'app_config.py'))) { throw 'Yanlis klasor. ZIP, BASLAT.bat bulunan kado klasorune acilmali.' }
    & $env:KADO_PY (Join-Path $bridgeDir 'worker.py') --check
    if ($LASTEXITCODE -ne 0) { throw 'Mevcut Kado Gemini anahtari okunamadi. Kado ayarlarini kontrol edin.' }
    if (-not (Test-Path 'node_modules\.kado-installed')) {
        Write-Host 'Ilk kurulum: WhatsApp yardimcilari, Chromium ve ses donusturucu indiriliyor. Biraz surebilir.'
        & npm.cmd ci --omit=dev --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw 'npm kurulumu tamamlanamadi. Yukaridaki hata satirini paylasin.' }
        & node check_runtime.js
        if ($LASTEXITCODE -ne 0) { throw 'Bagimlilik kontrolu basarisiz.' }
        New-Item -ItemType File 'node_modules\.kado-installed' -Force | Out-Null
    }
    & node bridge.js
    if ($LASTEXITCODE -ne 0) { throw 'WhatsApp modulu kapandi; yukaridaki hata satirini kontrol edin.' }
} catch { Write-Host $_.Exception.Message -ForegroundColor Red; exit 1 }
