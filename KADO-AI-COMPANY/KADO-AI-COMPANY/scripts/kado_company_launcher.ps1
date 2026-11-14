param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$CompanyRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$ConfigPath = Join-Path $CompanyRoot 'data\kado-connection.json'
if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw 'Once KADO_BAGLANTI_KUR.bat ile baglanti guncellemesini kurun.'
}
$Config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$ExistingRoot = [IO.Path]::GetFullPath([string]$Config.existing_root)
$AppDir = Join-Path $ExistingRoot 'sistem'
if (-not (Test-Path -LiteralPath (Join-Path $AppDir 'main.py'))) { $AppDir = $ExistingRoot }
$ExistingPython = Join-Path $AppDir '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $ExistingPython)) {
    throw 'Mevcut KADO Python ortami bulunamadi. Eski BASLAT.bat ile normal KADO kurulumunu kontrol edin.'
}
$Adapter = Join-Path $CompanyRoot 'kado_bridge\local_host.py'
$Arguments = @($Adapter, '--company-root', $CompanyRoot, '--kado-root', $ExistingRoot, '--url', [string]$Config.company_url)
if ($CheckOnly) { $Arguments += '--check' }
Write-Host 'Mevcut KADO kaynaklari degistirilmeden 35 ajanli sirket adaptoru aciliyor.'
Write-Host 'Eski KADO penceresi zaten aciksa once o pencereyi normal sekilde kapatin.'
& $ExistingPython @Arguments
exit $LASTEXITCODE
