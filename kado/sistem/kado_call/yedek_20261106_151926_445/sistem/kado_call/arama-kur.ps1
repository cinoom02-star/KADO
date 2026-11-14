$ErrorActionPreference = 'Stop'
try {
    $windowsScript = Join-Path $PSScriptRoot 'kur.sh'
    $distros = @(& wsl.exe --list --quiet | ForEach-Object { ($_ -replace '\x00','').Trim() } | Where-Object { $_ -like 'Ubuntu*' })
    $wslArgs = @()
    if ($distros.Count -gt 0) { $wslArgs = @('-d', $distros[0]) }
    $linuxScript = & wsl.exe @wslArgs -- wslpath -a $windowsScript
    if ($LASTEXITCODE -ne 0) { throw 'Ubuntu/WSL yolu okunamadi.' }
    $linuxScript = ($linuxScript | Select-Object -Last 1).Trim()
    & wsl.exe @wslArgs -- bash $linuxScript
    if ($LASTEXITCODE -ne 0) { throw 'Arama kurulumu tamamlanamadi. Yukaridaki hata satirini kontrol edin.' }
} catch { Write-Host $_.Exception.Message -ForegroundColor Red; exit 1 }
