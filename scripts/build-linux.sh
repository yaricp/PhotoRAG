#!/usr/bin/env bash
# build-linux.sh — Build the PhotoRAG Linux x86_64 AppImage.
#
# Run from the project root:
#   bash scripts/build-linux.sh
#
# Requirements:
#   • Node.js 20+  (npm in PATH)
#   • libfuse2     (Ubuntu 22.04+: sudo apt install libfuse2)
#
# Output: frontend/dist-electron/PhotoRAG-<version>-x86_64.AppImage

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND="$PROJECT_ROOT/frontend"

echo "=== PhotoRAG — Linux x86_64 AppImage Build ==="
echo ""

# ── Step 1: Download Linux Python runtime ────────────────────────────────────
echo "[1/3] Downloading Linux Python runtime..."
bash "$SCRIPT_DIR/download-python-linux.sh"

# ── Step 2: npm install ───────────────────────────────────────────────────────
echo ""
echo "[2/3] Installing npm dependencies..."
cd "$FRONTEND"
npm ci

# ── Step 3: Build AppImage ───────────────────────────────────────────────────
echo ""
echo "[3/3] Building Linux AppImage..."
npm run dist:linux

echo ""
echo "=== Build complete! ==="
echo "AppImage: $FRONTEND/dist-electron/"
ls -lh "$FRONTEND/dist-electron/"*.AppImage 2>/dev/null || echo "(check dist-electron/ for output)"
