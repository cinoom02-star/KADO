param([ValidateSet('kur','kontrol','geri')][string]$Islem='kontrol')
$ErrorActionPreference='Stop'
try {
    $target='C:\KADO\kado\sistem\kado_call'
    $location=Get-Content (Join-Path $target 'location.json') -Raw -Encoding UTF8|ConvertFrom-Json
    $hostText=Get-Content (Join-Path $target 'kado_host.py') -Raw -Encoding UTF8
    if($Islem -eq 'kur' -and !$hostText.Contains('Sade acilis V3:')) {
        throw 'Calisan V3 surumunde degilsiniz. Bu paket Kado host dosyasini degistirmez; once V3 kurun.'
    }
    $scripts=@{kur='patch_transport.py';kontrol='audit_transport.py';geri='restore_transport.py'}
    $d=@();if($location.distro){$d=@('-d',[string]$location.distro)}
    $windowsScript=(Join-Path $PSScriptRoot $scripts[$Islem]).Replace('\','/')
    $linuxScript=& wsl.exe @d -- wslpath -a $windowsScript
    if($LASTEXITCODE -ne 0){throw 'Ubuntu yolu okunamadi.'}
    $linuxScript=($linuxScript|Select-Object -Last 1).Trim()
    & wsl.exe @d -- python3 $linuxScript ([string]$location.directory)
    if($LASTEXITCODE -ne 0){throw 'Islem tamamlanamadi; yukaridaki hata satirini paylasin.'}
    if($Islem -eq 'kur') {
        Write-Host 'Kuruldu. V3 korunuyor. KADO_BIRLESIK_BASLAT.bat ile yeniden acin.' -ForegroundColor Green
        Write-Host 'Canli aramada 2-3 saniye henuz dogrulanmadi. ONCEKI MOTOR satirini saklayin.'
    }
} catch {Write-Host $_.Exception.Message -ForegroundColor Red;exit 1}
