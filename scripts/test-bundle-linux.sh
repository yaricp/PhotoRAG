#!/usr/bin/env bash
# test-bundle-linux.sh — Structural assertions on the built Linux AppImage.
# Run from the project root after `npm run dist:linux` completes.
#
# Usage:
#   bash scripts/test-bundle-linux.sh [path/to/dist-electron]
#
# If no path is provided it searches frontend/dist-electron/ for the first .AppImage.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DIST_DIR="${1:-$PROJECT_ROOT/frontend/dist-electron}"

APPIMAGE="$(find "$DIST_DIR" -maxdepth 2 -name "*.AppImage" | head -1)"
if [[ -z "$APPIMAGE" ]]; then
    echo "ERROR: No .AppImage found in $DIST_DIR"
    exit 1
fi

echo "[test-bundle-linux] Testing: $APPIMAGE"

# Extract squashfs without mounting (no FUSE required in CI)
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

SQUASH_DIR="$WORK_DIR/squashfs"
# AppImages support --appimage-extract which dumps to squashfs-root/
pushd "$WORK_DIR" > /dev/null
"$APPIMAGE" --appimage-extract > /dev/null 2>&1 || {
    echo "ERROR: --appimage-extract failed"
    exit 1
}
popd > /dev/null
mv "$WORK_DIR/squashfs-root" "$SQUASH_DIR"

RESOURCES="$SQUASH_DIR/resources"

PASS=0
FAIL=0

assert_exists() {
    local rel="$1"
    local full="$RESOURCES/$rel"
    if [[ -e "$full" ]]; then
        echo "  ✓ exists:     $rel"
        (( PASS++ )) || true
    else
        echo "  ✗ MISSING:    $rel"
        (( FAIL++ )) || true
    fi
}

assert_executable() {
    local rel="$1"
    local full="$RESOURCES/$rel"
    if [[ -x "$full" ]]; then
        echo "  ✓ executable: $rel"
        (( PASS++ )) || true
    else
        echo "  ✗ NOT EXEC:   $rel"
        (( FAIL++ )) || true
    fi
}

echo ""
echo "=== Python runtime ==="
assert_exists     "python/bin/python3"
assert_executable "python/bin/python3"

echo ""
echo "=== Backend source ==="
assert_exists "backend/run.py"
assert_exists "backend/src/main.py"
assert_exists "backend/src/config.py"
assert_exists "backend/requirements.txt"

echo ""
echo "=== Python version ==="
PY="$RESOURCES/python/bin/python3"
if [[ -x "$PY" ]]; then
    PY_VER="$("$PY" --version 2>&1)"
    echo "  ✓ $PY_VER"
    (( PASS++ )) || true
else
    echo "  ✗ python3 not executable — skipping version check"
    (( FAIL++ )) || true
fi

echo ""
echo "=== Summary ==="
echo "  Passed: $PASS"
echo "  Failed: $FAIL"
echo ""

if (( FAIL > 0 )); then
    echo "BUNDLE STRUCTURE TEST FAILED ($FAIL assertions failed)"
    exit 1
else
    echo "All bundle structure assertions passed."
    exit 0
fi
