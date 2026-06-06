#!/usr/bin/env bash
# build-mac.sh — Full macOS build pipeline.
# Run from the project root.
#
# Steps:
#   1. Download / verify universal Python runtime
#   2. Install frontend npm dependencies
#   3. Build Electron app + package as .dmg

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo "=== Step 1: Download Python runtime ==="
bash "$SCRIPT_DIR/download-python.sh"

echo ""
echo "=== Step 2: Install npm dependencies ==="
cd "$FRONTEND_DIR"
npm ci

echo ""
echo "=== Step 3: Build and package ==="
npm run dist:mac

echo ""
echo "=== Build complete ==="
echo "Artifacts in: $FRONTEND_DIR/dist-electron/"
