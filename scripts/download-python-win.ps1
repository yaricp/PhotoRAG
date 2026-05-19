# download-python-win.ps1 — Download python-build-standalone for Windows x64
# and unpack it into frontend\resources\python\.
#
# Idempotent: skips the download if the version file matches the target release.
# Run from the project root (or from scripts\):
#   powershell -ExecutionPolicy Bypass -File scripts\download-python-win.ps1
#
# Requires: Windows 10 1803+ (tar with gzip support is built-in)

param()
$ErrorActionPreference = "Stop"

$ScriptDir   = Split-Path $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path $ScriptDir
$OutDir      = "$ProjectRoot\frontend\resources\python"
$VersionFile = "$OutDir\.python_version"

# ── Release pin (keep in sync with download-python-win.sh) ────────────────────
$ReleaseTag    = "20260510"
$PyVersion     = "3.13.13"
$Arch          = "x86_64-pc-windows-msvc-install_only"
$Filename      = "cpython-${PyVersion}+${ReleaseTag}-${Arch}.tar.gz"
$BaseUrl       = "https://github.com/astral-sh/python-build-standalone/releases/download/${ReleaseTag}"
$TargetVersion = "${PyVersion}+${ReleaseTag}-win-x64"

# ── Idempotency check ─────────────────────────────────────────────────────────
if ((Test-Path $VersionFile) -and ((Get-Content $VersionFile) -eq $TargetVersion)) {
    Write-Host "[download-python-win] Already at $TargetVersion — skipping."
    exit 0
}

Write-Host "[download-python-win] Downloading Python $PyVersion for Windows x64..."

$TempDir = [System.IO.Path]::GetTempPath() + [System.Guid]::NewGuid().ToString()
New-Item -ItemType Directory -Path $TempDir | Out-Null
$Archive = "$TempDir\cpython-win.tar.gz"

try {
    # Use curl.exe (built-in on Win 10 1803+) for better progress and retry
    curl.exe -fSL --retry 3 "$BaseUrl/$Filename" -o $Archive

    Write-Host "[download-python-win] Extracting..."
    if (Test-Path $OutDir) { Remove-Item $OutDir -Recurse -Force }
    New-Item -ItemType Directory -Path $OutDir | Out-Null

    tar -xzf $Archive -C $OutDir --strip-components=1

    # ── Verify ────────────────────────────────────────────────────────────────
    $PyExe = "$OutDir\python.exe"
    if (-not (Test-Path $PyExe)) {
        Write-Host "[download-python-win] ERROR: python.exe not found after extraction."
        Write-Host "  Contents of ${OutDir}:"
        Get-ChildItem $OutDir | Select-Object -First 20 | Format-Table Name, Length
        Write-Host "  The archive layout may differ — check --strip-components."
        exit 1
    }
    Write-Host "[download-python-win] Found: $PyExe"

    # ── Write version stamp ───────────────────────────────────────────────────
    Set-Content -Path $VersionFile -Value $TargetVersion
    Write-Host "[download-python-win] Done. Windows Python runtime ready at $OutDir"
}
finally {
    Remove-Item $TempDir -Recurse -Force -ErrorAction SilentlyContinue
}
