#!/usr/bin/env bash
# test-bundle-win.sh — Smoke-test the Windows NSIS installer artifact.
#
# Run from the project root (after npm run dist:win):
#   bash scripts/test-bundle-win.sh
#
# Checks that the .exe was produced and meets minimum size expectations.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST="$SCRIPT_DIR/../frontend/dist-electron"

echo "=== Windows bundle verification ==="

# ── Check .exe exists ─────────────────────────────────────────────────────────
EXE=$(find "$DIST" -maxdepth 1 -name "*.exe" | head -1)
if [[ -z "$EXE" ]]; then
    echo "FAIL: No .exe found in $DIST"
    echo "Contents:"
    ls -la "$DIST" 2>/dev/null || echo "  (directory missing)"
    exit 1
fi
echo "✓ Installer: $EXE"

# ── Size sanity check (installer should be > 50 MB) ──────────────────────────
SIZE_BYTES=$(wc -c < "$EXE")
SIZE_MB=$(( SIZE_BYTES / 1024 / 1024 ))
if (( SIZE_MB < 50 )); then
    echo "FAIL: Installer is only ${SIZE_MB} MB — expected > 50 MB (Python runtime likely missing)"
    exit 1
fi
echo "✓ Size: ${SIZE_MB} MB"

# ── Check unpacked dir exists (electron-builder also produces a --win unpacked folder) ─
UNPACKED=$(find "$DIST" -maxdepth 1 -name "win-unpacked" -type d | head -1)
if [[ -n "$UNPACKED" ]]; then
    echo "✓ Unpacked dir: $UNPACKED"

    # Verify key files inside the unpacked app
    declare -a REQUIRED=(
        "resources/python/python.exe"
        "resources/backend/run.py"
        "resources/backend/requirements.txt"
        "resources/backend/src"
        "resources/app.asar"
    )
    for rel in "${REQUIRED[@]}"; do
        if [[ ! -e "$UNPACKED/$rel" ]]; then
            echo "FAIL: Missing expected file: $UNPACKED/$rel"
            exit 1
        fi
        echo "✓ $rel"
    done
else
    echo "NOTE: win-unpacked directory not found — skipping deep inspection"
    echo "      (add '--dir' to dist:win to generate it for local testing)"
fi

echo ""
echo "=== All checks passed ==="
