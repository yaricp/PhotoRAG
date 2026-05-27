#!/usr/bin/env bash
# download-python-linux.sh — Download python-build-standalone for Linux x86_64
# and unpack it into frontend/resources/python/.
#
# Idempotent: skips the download if the version file matches the target release.
# Run from the project root:
#   bash scripts/download-python-linux.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="$PROJECT_ROOT/frontend/resources/python"
VERSION_FILE="$OUT_DIR/.python_version"

# ── Release pin (keep in sync with download-python.sh / download-python-win.sh) ─
RELEASE_TAG="20260510"
PY_VERSION="3.13.13"
ARCH="x86_64-unknown-linux-gnu-install_only"
FILENAME="cpython-${PY_VERSION}+${RELEASE_TAG}-${ARCH}.tar.gz"
BASE_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${RELEASE_TAG}"
TARGET_VERSION="${PY_VERSION}+${RELEASE_TAG}-linux-x64"

# ── Idempotency check ─────────────────────────────────────────────────────────
if [[ -f "$VERSION_FILE" ]] && [[ "$(cat "$VERSION_FILE")" == "$TARGET_VERSION" ]]; then
    echo "[download-python-linux] Already at $TARGET_VERSION — skipping."
    exit 0
fi

echo "[download-python-linux] Downloading Python ${PY_VERSION} for Linux x86_64..."

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

curl -fSL --retry 3 "$BASE_URL/$FILENAME" -o "$WORK_DIR/cpython-linux.tar.gz"

echo "[download-python-linux] Extracting..."
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"
tar -xzf "$WORK_DIR/cpython-linux.tar.gz" -C "$OUT_DIR" --strip-components=1

# ── Verify ────────────────────────────────────────────────────────────────────
PY_BIN="$OUT_DIR/bin/python3"
if [[ ! -f "$PY_BIN" ]]; then
    echo "[download-python-linux] ERROR: python3 not found after extraction."
    echo "  Contents of $OUT_DIR/bin/:"
    ls -la "$OUT_DIR/bin/" 2>/dev/null | head -20
    exit 1
fi

"$PY_BIN" --version \
    || { echo "[download-python-linux] ERROR: python3 --version failed"; exit 1; }

# ── Write version stamp ───────────────────────────────────────────────────────
echo "$TARGET_VERSION" > "$VERSION_FILE"
echo "[download-python-linux] Done. Linux Python runtime ready at $OUT_DIR"
