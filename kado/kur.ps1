$ErrorActionPreference='Stop'
try {
    $target='C:\KADO\kado\sistem\kado_call'
    $location=Get-Content (Join-Path $target 'location.json') -Raw|ConvertFrom-Json
    $d=@();if($location.distro){$d=@('-d',[string]$location.distro)}
    $windowsScript=(Join-Path $PSScriptRoot 'patch_simple.py').Replace('\','/')
    $linuxScript=& wsl.exe @d -- wslpath -a $windowsScript
    if($LASTEXITCODE -ne 0){throw 'Ubuntu yolu okunamadi.'}
    $linuxScript=($linuxScript|Select-Object -Last 1).Trim()
    & wsl.exe @d -- python3 $linuxScript ([string]$location.directory)
    if($LASTEXITCODE -ne 0){throw 'Arama akisi guncellenemedi. Kado dosyasi degistirilmedi.'}
    $hostFile=Join-Path $target 'kado_host.py'
    Copy-Item $hostFile ($hostFile+'.sade-oncesi-'+(Get-Date -Format 'yyyyMMddHHmmss'))
    Copy-Item (Join-Path $PSScriptRoot 'kado_host.py') $hostFile -Force
    Write-Host 'Kuruldu. KADO_BIRLESIK_BASLAT.bat ile yeniden acabilirsiniz.' -ForegroundColor Green
} catch {Write-Host $_.Exception.Message -ForegroundColor Red;exit 1}
