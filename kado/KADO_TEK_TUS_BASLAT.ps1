$ErrorActionPreference = "Stop"

$root = "C:\KADO"
$app = Join-Path $root "kado"
$agents = Join-Path $root "KADO-AJANLAR"

$combined = Join-Path $app "KADO_BIRLESIK_BASLAT.bat"
$panel = Join-Path $agents "kado_tek_panel_v4.py"
$python = Join-Path $agents ".venv\Scripts\python.exe"

Write-Host ""
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "       KADO TEK TUS BASLATICI" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan

foreach ($file in @($combined, $panel, $python)) {
    if (!(Test-Path -LiteralPath $file)) {
        throw "Eksik dosya: $file"
    }
}

# Mevcut KADO motorunu ve WhatsApp zincirini
# ayri bir pencerede baslat.
Write-Host "KADO ana motoru ve WhatsApp baslatiliyor..."

Start-Process -FilePath "cmd.exe" `
    -ArgumentList @("/k", "`"$combined`"") `
    -WorkingDirectory $app | Out-Null

# Ajan paneli ayri bir pencerede calisir.
# Panelin acilmasi ajan toplantisi baslatmaz.
Write-Host "KADO V4 ajan paneli baslatiliyor..."

Start-Process -FilePath $python `
    -ArgumentList @("-u", "`"$panel`"") `
    -WorkingDirectory $agents | Out-Null

Write-Host ""
Write-Host "Baslatma komutlari gonderildi." -ForegroundColor Green
Write-Host "Ajanlar yalnizca panelden gorev verildiginde calisir."
Write-Host "Gemini API otomatik cagrilmadi."
Write-Host ""
Write-Host "Panel adresini ajan paneli konsolundan kontrol edin."
