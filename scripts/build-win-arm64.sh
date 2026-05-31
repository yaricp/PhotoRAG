#!/usr/bin/env bash
# build-win-arm64.sh — Build the PhotoRAG Windows ARM64 NSIS installer.
#
# Cross-compiles from any host (macOS, Linux, or Windows x64 via Git Bash).
# electron-builder downloads the arm64 Electron binary automatically.
#
# Run from the project root:
#   bash scripts/build-win-arm64.sh
#
# Output: frontend/dist-electron/PhotoRAG-Setup-<version>-arm64.exe

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND="$PROJECT_ROOT/frontend"

echo "=== PhotoRAG — Windows ARM64 NSIS Installer Build ==="
echo ""

# ── Step 1: Download Windows ARM64 Python runtime ────────────────────────────
echo "[1/3] Downloading Windows ARM64 Python runtime..."
bash "$SCRIPT_DIR/download-python-win-arm64.sh"

# ── Step 2: npm install ───────────────────────────────────────────────────────
echo ""
echo "[2/3] Installing npm dependencies..."
cd "$FRONTEND"
npm ci

# ── Step 3: Build NSIS ARM64 installer ───────────────────────────────────────
echo ""
echo "[3/3] Building Windows ARM64 NSIS installer..."
npm run dist:win:arm64

echo ""
echo "=== Build complete! ==="
echo "Installer: $FRONTEND/dist-electron/"
ls -lh "$FRONTEND/dist-electron/"*arm64*.exe 2>/dev/null || echo "(check dist-electron/ for output)"
