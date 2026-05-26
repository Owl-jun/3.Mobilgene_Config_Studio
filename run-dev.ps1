# Mobilgene Config Studio — development server
param([switch]$Background)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $env:MCS_PORT) { $env:MCS_PORT = "8765" }

# 이전 서버가 남아 있으면 구 API → module_graph not_found 발생
$onPort = Get-NetTCPConnection -LocalPort $env:MCS_PORT -ErrorAction SilentlyContinue
if ($onPort) {
    $onPort | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
        Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1
    Write-Host "Stopped previous process on port $env:MCS_PORT"
}

$DefaultWorkspace = Join-Path $Root "..\2.AD_Gateway\AD_Gateway\rgw_working"
if (-not $env:MCS_WORKSPACE -and (Test-Path $DefaultWorkspace)) {
    $env:MCS_WORKSPACE = (Resolve-Path $DefaultWorkspace).Path
}

$python = (Get-Command python -ErrorAction Stop).Source
$serverScript = Join-Path $Root "scripts\dev_server.py"
$url = "http://127.0.0.1:$env:MCS_PORT"

Write-Host ""
Write-Host "Mobilgene Config Studio"
Write-Host "  Server : $url"
if ($env:MCS_WORKSPACE) { Write-Host "  Workspace : $env:MCS_WORKSPACE" }
Write-Host "  Stop   : Ctrl+C"
Write-Host ""

if ($Background) {
    Start-Process -FilePath $python -ArgumentList @($serverScript) -WorkingDirectory $Root -WindowStyle Hidden
    Write-Host "Server started in background."
    exit 0
}

Set-Location $Root
try {
    Start-Process $url
} catch {
    Write-Host "브라우저를 직접 여세요: $url"
}

& $python $serverScript
