#!/usr/bin/env bash
# build-linux-arm64.sh — Build the PhotoRAG Linux ARM64 AppImage.
#
# Run this on an ARM64 Linux machine (Raspberry Pi 4/5, AWS Graviton,
# Apple Silicon VM, etc.) or cross-compile from any host where
# electron-builder can target linux/arm64.
#
# Run from the project root:
#   bash scripts/build-linux-arm64.sh
#
# Requirements:
#   • Node.js 20+  (npm in PATH)
#   • libfuse2     (to run the resulting AppImage on Linux ARM64:
#                   sudo apt install libfuse2)
#
# Output: frontend/dist-electron/PhotoRAG-<version>-arm64.AppImage

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND="$PROJECT_ROOT/frontend"

echo "=== PhotoRAG — Linux ARM64 AppImage Build ==="
echo ""

# ── Step 1: Download Linux ARM64 Python runtime ───────────────────────────────
echo "[1/3] Downloading Linux ARM64 Python runtime..."
bash "$SCRIPT_DIR/download-python-linux.sh" arm64

# ── Step 2: npm install ───────────────────────────────────────────────────────
echo ""
echo "[2/3] Installing npm dependencies..."
cd "$FRONTEND"
npm ci

# ── Step 3: Build AppImage ───────────────────────────────────────────────────
echo ""
echo "[3/3] Building Linux ARM64 AppImage..."
npm run dist:linux:arm64

echo ""
echo "=== Build complete! ==="
echo "AppImage: $FRONTEND/dist-electron/"
ls -lh "$FRONTEND/dist-electron/"*arm64*.AppImage 2>/dev/null || echo "(check dist-electron/ for output)"
