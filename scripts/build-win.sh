#!/usr/bin/env bash
# build-win.sh — Build the PhotoRAG Windows NSIS installer.
#
# Works on:
#   • macOS  — cross-compiles via electron-builder (requires zstd: brew install zstd)
#   • Linux  — cross-compiles via electron-builder (requires zstd: apt install zstd)
#   • Windows (Git Bash / MSYS2) — native build
#
# Run from the project root:
#   bash scripts/build-win.sh
#
# Output: frontend/dist-electron/PhotoRAG-Setup-<version>-x64.exe

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND="$PROJECT_ROOT/frontend"

echo "=== PhotoRAG — Windows x64 NSIS Installer Build ==="
echo ""

# ── Step 1: Download Windows Python runtime ───────────────────────────────────
echo "[1/3] Downloading Windows Python runtime..."
bash "$SCRIPT_DIR/download-python-win.sh"

# ── Step 2: npm install ───────────────────────────────────────────────────────
echo ""
echo "[2/3] Installing npm dependencies..."
cd "$FRONTEND"
npm install

# ── Step 3: Build NSIS installer ──────────────────────────────────────────────
echo ""
echo "[3/3] Building Windows NSIS installer..."
npm run dist:win

echo ""
echo "=== Build complete! ==="
echo "Installer: $FRONTEND/dist-electron/"
ls -lh "$FRONTEND/dist-electron/"*.exe 2>/dev/null || echo "(check dist-electron/ for output)"
