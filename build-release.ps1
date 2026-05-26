# Mobilgene Config Studio — 1차 배포 빌드 (Windows portable)
# 빌드 PC: Python 3.10+ 필요. 결과물은 대상 PC에 Python/Node 불필요.
param(
    [switch]$SkipTauri,
    [switch]$Zip
)
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

function Stop-McsProcesses {
    Get-Process -Name "MobilgeneConfigStudio" -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

Write-Host ""
Write-Host "=== Mobilgene Config Studio - Release Build ===" -ForegroundColor Cyan
Write-Host ""

Stop-McsProcesses

$python = Get-Command python -ErrorAction Stop
Write-Host "Python: $($python.Source)"

& python -m pip install --upgrade pip -q
& python -m pip install pyinstaller -q

$distDir = Join-Path $Root "dist\MobilgeneConfigStudio"
$buildDir = Join-Path $Root "build\pyinstaller"

if (Test-Path $distDir) {
    Remove-Item -Recurse -Force $distDir
}

Write-Host "PyInstaller (onedir portable)..." -ForegroundColor Yellow
& python -m PyInstaller `
    (Join-Path $Root "packaging\mobilgene.spec") `
    --noconfirm `
    --distpath (Join-Path $Root "dist") `
    --workpath $buildDir

if (-not (Test-Path (Join-Path $distDir "MobilgeneConfigStudio.exe"))) {
    throw "Build failed: MobilgeneConfigStudio.exe not found"
}

$bat = @"
@echo off
cd /d "%~dp0"
title Mobilgene Config Studio
echo Starting Mobilgene Config Studio...
MobilgeneConfigStudio.exe
if errorlevel 1 pause
"@
Set-Content -Path (Join-Path $distDir "Start.bat") -Value $bat -Encoding ASCII

$readmeKo = Join-Path $Root "packaging\README-portable-ko.txt"
if (-not (Test-Path $readmeKo)) {
    throw "Missing packaging\README-portable-ko.txt"
}
Copy-Item -Path $readmeKo -Destination (Join-Path $distDir "README.txt") -Force

Write-Host ""
Write-Host "[OK] Portable build:" -ForegroundColor Green
Write-Host "     $distDir"
Write-Host "     Run: Start.bat" -ForegroundColor Green
Write-Host ""

$zipOk = $false
if ($Zip) {
    Stop-McsProcesses
    $zipPath = Join-Path $Root "dist\MobilgeneConfigStudio-0.1.0-win64.zip"
    if (Test-Path $zipPath) { Remove-Item -Force $zipPath }

    $tar = Get-Command tar.exe -ErrorAction SilentlyContinue
    if ($tar) {
        Push-Location (Join-Path $Root "dist")
        try {
            & tar.exe -a -cf $zipPath "MobilgeneConfigStudio"
            if ($LASTEXITCODE -eq 0 -and (Test-Path $zipPath)) {
                $zipOk = $true
                Write-Host "[OK] ZIP: $zipPath" -ForegroundColor Green
            }
        } finally {
            Pop-Location
        }
    }
    if (-not $zipOk) {
        Write-Host "[WARN] ZIP failed. Copy folder instead:" -ForegroundColor Yellow
        Write-Host "       $distDir"
        Write-Host "       (Close MobilgeneConfigStudio.exe if running, then re-run with -Zip)" -ForegroundColor Yellow
    }
}

if (-not $SkipTauri) {
    $cargo = Get-Command cargo -ErrorAction SilentlyContinue
    if (-not $cargo) {
        Write-Host "[SKIP] Tauri: Rust/cargo not installed (portable folder is enough)" -ForegroundColor Yellow
    } else {
        $tauriOk = $false
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & cargo tauri --version 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[SKIP] Tauri: 'cargo tauri' not installed." -ForegroundColor Yellow
            Write-Host "       Install: cargo install tauri-cli --locked" -ForegroundColor Yellow
            Write-Host "       Or use: .\build-release.ps1 -SkipTauri -Zip" -ForegroundColor Yellow
        } else {
            Write-Host "Tauri build (optional installer)..." -ForegroundColor Yellow
            $binDir = Join-Path $Root "src-tauri\bin"
            New-Item -ItemType Directory -Force -Path $binDir | Out-Null
            Copy-Item (Join-Path $distDir "MobilgeneConfigStudio.exe") `
                (Join-Path $binDir "mcs-server-x86_64-pc-windows-msvc.exe") -Force
            Push-Location (Join-Path $Root "src-tauri")
            try {
                & cargo tauri build 2>&1 | ForEach-Object { Write-Host $_ }
                if ($LASTEXITCODE -eq 0) {
                    $tauriOk = $true
                    Write-Host "[OK] Tauri: src-tauri\target\release\bundle\" -ForegroundColor Green
                } else {
                    Write-Host "[WARN] Tauri build failed (portable build is still valid)" -ForegroundColor Yellow
                }
            } finally {
                Pop-Location
            }
        }
        $ErrorActionPreference = $prevEap
    }
}

Write-Host ""
Write-Host "=== Release ready ===" -ForegroundColor Cyan
Write-Host "Deploy: copy dist\MobilgeneConfigStudio to target PC, run Start.bat"
Write-Host ""
