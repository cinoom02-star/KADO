param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('Install','Start','Stop','Test','Status')]
    [string]$Action
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')).TrimEnd('\')
$DataDir = Join-Path $ProjectRoot 'data'
$PidFile = Join-Path $DataDir 'company-process.json'
$PythonPath = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$BackendPath = Join-Path $ProjectRoot 'backend'

function Assert-SeparateFolder {
    foreach ($protected in @('C:\KADO\kado','C:\KADO\KADO-AJANLAR')) {
        if ($ProjectRoot.Equals($protected, [StringComparison]::OrdinalIgnoreCase) -or
            $ProjectRoot.StartsWith($protected + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Bu paket mevcut KADO klasorune kurulamaz. Ornek: C:\KADO\KADO-AI-COMPANY'
        }
    }
    $current = Get-Item -LiteralPath $ProjectRoot
    while ($null -ne $current -and $null -ne $current.Parent) {
        if (($current.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Kurulum yolunda baglanti/junction var. Ayri, normal bir klasor secin.'
        }
        $current = $current.Parent
    }
}

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw ('Komut basarisiz: ' + $Executable + ' (kod ' + $LASTEXITCODE + ')') }
}

function Get-OwnedProcess {
    if (-not (Test-Path -LiteralPath $PidFile)) { return $null }
    $record = Get-Content -LiteralPath $PidFile -Raw | ConvertFrom-Json
    $process = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + [int]$record.process_id) -ErrorAction Stop
    if ($null -eq $process) { return $null }
    $live = Get-Process -Id ([int]$record.process_id) -ErrorAction Stop
    $actualPath = [string]$process.ExecutablePath
    $actualCommand = [string]$process.CommandLine
    if (-not $actualPath.Equals($PythonPath, [StringComparison]::OrdinalIgnoreCase) -or
        -not $actualCommand.Contains('company.api:app') -or
        $actualCommand.IndexOf($BackendPath, [StringComparison]::OrdinalIgnoreCase) -lt 0 -or
        ([string]($live.StartTime.ToUniversalTime().Ticks)) -ne ([string]$record.start_ticks)) {
        throw 'PID baska bir surece ait olabilir. Guvenli durdurma reddedildi; company-process.json kaydini inceleyin.'
    }
    return $live
}

Assert-SeparateFolder
Push-Location -LiteralPath $ProjectRoot
try {
    if ($Action -eq 'Install') {
        if (-not (Get-Command node -ErrorAction SilentlyContinue) -or -not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
            throw 'Node.js 22+ ve npm kurun; yeni bir terminal acip yeniden deneyin.'
        }
        Invoke-Checked 'node' @('-e','if(Number(process.versions.node.match(/^[0-9]+/)[0])<22)process.exit(1)')
        if (-not (Test-Path -LiteralPath $PythonPath)) {
            if (Get-Command py -ErrorAction SilentlyContinue) {
                Invoke-Checked 'py' @('-3.12','-m','venv','.venv')
            } else {
                Invoke-Checked 'python' @('-c','import sys; sys.exit(0 if sys.version_info[:2] == (3,12) else 1)')
                Invoke-Checked 'python' @('-m','venv','.venv')
            }
        }
        Invoke-Checked $PythonPath @('-c','import sys; sys.exit(0 if sys.version_info[:2] == (3,12) else 1)')
        Invoke-Checked $PythonPath @('-m','pip','install','-r','requirements.txt')
        Invoke-Checked 'npm.cmd' @('--prefix','frontend','ci')
        Invoke-Checked 'npm.cmd' @('--prefix','frontend','run','build')
        New-Item -ItemType Directory -Force -Path (Join-Path $DataDir 'workspace') | Out-Null
        Write-Host 'Kurulum tamamlandi. BASLAT.bat ile baslatin. Mevcut KADO dosyalari degistirilmedi.'
    } elseif ($Action -eq 'Start') {
        if (-not (Test-Path -LiteralPath $PythonPath)) { throw 'Once KURULUM.bat calistirin.' }
        if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot 'frontend\dist\index.html'))) { throw 'Panel derlenmemis. KURULUM.bat calistirin.' }
        $existing = Get-OwnedProcess
        if ($null -ne $existing) {
            Write-Host 'Bu paket zaten calisiyor: http://127.0.0.1:8765'
            exit 0
        }
        try {
            Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/health' -TimeoutSec 2 | Out-Null
            throw '8765 portunda bir servis var; mevcut servisi degistirmeden port cakismasini giderin.'
        } catch [System.Net.WebException] {
            # Yerel servis yok; baslatma devam eder.
        }
        New-Item -ItemType Directory -Force -Path (Join-Path $DataDir 'logs') | Out-Null
        $arguments = @('-m','uvicorn','company.api:app','--app-dir',('"' + $BackendPath + '"'),'--host','127.0.0.1','--port','8765')
        $process = Start-Process -FilePath $PythonPath -ArgumentList $arguments -WorkingDirectory $ProjectRoot -PassThru `
            -RedirectStandardOutput (Join-Path $DataDir 'logs\backend.log') `
            -RedirectStandardError (Join-Path $DataDir 'logs\backend-error.log')
        Start-Sleep -Milliseconds 300
        $process.Refresh()
        if ($process.HasExited) { throw 'Backend baslatilamadi. data\logs\backend-error.log dosyasini inceleyin.' }
        @{ process_id=$process.Id; start_ticks=([string]($process.StartTime.ToUniversalTime().Ticks)); project_root=$ProjectRoot } |
            ConvertTo-Json | Set-Content -LiteralPath $PidFile -Encoding UTF8
        $ready = $false
        for ($attempt=0; $attempt -lt 30; $attempt++) {
            if ($process.HasExited) { break }
            try {
                Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/health' -TimeoutSec 1 | Out-Null
                $ready=$true; break
            } catch { Start-Sleep -Milliseconds 500; $process.Refresh() }
        }
        if (-not $ready) { throw 'Saglik kontrolu basarisiz. Gunlukleri inceleyin; PID kaydi korunuyor.' }
        Write-Host 'Panel: http://127.0.0.1:8765'
        Write-Host 'Panel token dosyasi: data\api-token.txt (KADO_API_TOKEN belirtilmediyse).'
        Start-Process 'http://127.0.0.1:8765'
    } elseif ($Action -eq 'Stop') {
        $process = Get-OwnedProcess
        if ($null -eq $process) {
            Write-Host 'Bu pakete ait calisan surec bulunamadi.'
        } else {
            Stop-Process -Id $process.Id -ErrorAction Stop
            Write-Host 'Yalnizca bu paketin backend sureci durduruldu.'
        }
        if (Test-Path -LiteralPath $PidFile) { Remove-Item -LiteralPath $PidFile }
    } elseif ($Action -eq 'Test') {
        if (-not (Test-Path -LiteralPath $PythonPath)) { throw 'Once KURULUM.bat calistirin.' }
        Invoke-Checked $PythonPath @('-m','pytest','-q')
        Invoke-Checked 'npm.cmd' @('--prefix','frontend','run','build')
        Write-Host 'Yerel kod testleri tamamlandi. Gercek WhatsApp/arama testi bu komuta dahil degildir.'
    } else {
        $process = Get-OwnedProcess
        if ($null -eq $process) { Write-Host 'Durum: calismiyor' } else { Write-Host ('Durum: calisiyor, PID ' + $process.Id) }
    }
} finally {
    Pop-Location
}
