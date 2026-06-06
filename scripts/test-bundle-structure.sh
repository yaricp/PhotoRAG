#!/usr/bin/env bash
# test-bundle-structure.sh — Structural assertions on the built .app bundle.
# Run from the project root after `npm run dist:mac` completes.
#
# Usage:
#   bash scripts/test-bundle-structure.sh [path/to/dist-electron]
#
# If no path is provided it searches frontend/dist-electron/ for the first .app.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DIST_DIR="${1:-$PROJECT_ROOT/frontend/dist-electron}"

# Find the .app bundle
APP_PATH="$(find "$DIST_DIR" -maxdepth 2 -name "*.app" -type d | head -1)"
if [[ -z "$APP_PATH" ]]; then
    echo "ERROR: No .app bundle found in $DIST_DIR"
    exit 1
fi

echo "[test-bundle] Testing: $APP_PATH"

PASS=0
FAIL=0

assert_exists() {
    local rel="$1"
    local full="$APP_PATH/Contents/Resources/$rel"
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
    local full="$APP_PATH/Contents/Resources/$rel"
    if [[ -x "$full" ]]; then
        echo "  ✓ executable: $rel"
        (( PASS++ )) || true
    else
        echo "  ✗ NOT EXEC:   $rel"
        (( FAIL++ )) || true
    fi
}

assert_universal() {
    local rel="$1"
    local full="$APP_PATH/Contents/Resources/$rel"
    if lipo -info "$full" 2>/dev/null | grep -qE "arm64.*x86_64|x86_64.*arm64|Non-fat.*universal"; then
        echo "  ✓ universal:  $rel"
        (( PASS++ )) || true
    elif lipo -info "$full" 2>/dev/null | grep -q "arm64" && lipo -info "$full" 2>/dev/null | grep -q "x86_64"; then
        echo "  ✓ universal:  $rel"
        (( PASS++ )) || true
    else
        local info; info="$(lipo -info "$full" 2>&1 || echo 'N/A')"
        echo "  ✗ NOT UNIV:   $rel  ($info)"
        (( FAIL++ )) || true
    fi
}

echo ""
echo "=== Python runtime ==="
assert_exists     "python/bin/python3"
assert_executable "python/bin/python3"
assert_universal  "python/bin/python3"

echo ""
echo "=== Backend source ==="
assert_exists "backend/run.py"
assert_exists "backend/src/main.py"
assert_exists "backend/src/config.py"
assert_exists "backend/src/data_dir.py"
assert_exists "backend/requirements.txt"

echo ""
echo "=== Python version ==="
PY="$APP_PATH/Contents/Resources/python/bin/python3"
PY_VER="$("$PY" --version 2>&1)"
echo "  ✓ $PY_VER"

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
