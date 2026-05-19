# build-win.ps1 — Build the PhotoRAG Windows NSIS installer (native Windows).
#
# Run from the project root:
#   powershell -ExecutionPolicy Bypass -File scripts\build-win.ps1
#
# Requires: Node.js 20+, npm, Windows 10 1803+ (tar with zstd support built-in)
# Output:   frontend\dist-electron\PhotoRAG-Setup-<version>-x64.exe

param()
$ErrorActionPreference = "Stop"

$ScriptDir   = Split-Path $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path $ScriptDir
$Frontend    = "$ProjectRoot\frontend"

Write-Host "=== PhotoRAG — Windows x64 NSIS Installer Build ===" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Download Windows Python runtime ────────────────────────────────────
Write-Host "[1/3] Downloading Windows Python runtime..." -ForegroundColor Yellow
& powershell -ExecutionPolicy Bypass -File "$ScriptDir\download-python-win.ps1"

# ── Step 2: npm install ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/3] Installing npm dependencies..." -ForegroundColor Yellow
Set-Location $Frontend
npm install

# ── Step 3: Build NSIS installer ───────────────────────────────────────────────
Write-Host ""
Write-Host "[3/3] Building Windows NSIS installer..." -ForegroundColor Yellow
npm run dist:win

Write-Host ""
Write-Host "=== Build complete! ===" -ForegroundColor Green
$Exe = Get-ChildItem "$Frontend\dist-electron\*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($Exe) {
    Write-Host "Installer: $($Exe.FullName) ($([math]::Round($Exe.Length / 1MB, 1)) MB)"
} else {
    Write-Host "Check frontend\dist-electron\ for output."
}
