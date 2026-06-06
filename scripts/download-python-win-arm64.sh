#!/usr/bin/env bash
# download-python-win-arm64.sh — Download python-build-standalone for Windows ARM64
# and unpack it into frontend/resources/python/.
#
# Idempotent: skips the download if the version file matches the target release.
# Run from the project root:
#   bash scripts/download-python-win-arm64.sh
#
# Works on macOS, Linux, and Windows (Git Bash / MSYS2).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="$PROJECT_ROOT/frontend/resources/python"
VERSION_FILE="$OUT_DIR/.python_version"

# ── Release pin (keep in sync with download-python-win.sh) ───────────────────
RELEASE_TAG="20260510"
PY_VERSION="3.13.13"
ARCH="aarch64-pc-windows-msvc-install_only"
FILENAME="cpython-${PY_VERSION}+${RELEASE_TAG}-${ARCH}.tar.gz"
BASE_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${RELEASE_TAG}"
TARGET_VERSION="${PY_VERSION}+${RELEASE_TAG}-win-arm64"

# ── Idempotency check ─────────────────────────────────────────────────────────
if [[ -f "$VERSION_FILE" ]] && [[ "$(cat "$VERSION_FILE")" == "$TARGET_VERSION" ]]; then
    echo "[download-python-win-arm64] Already at $TARGET_VERSION — skipping."
    exit 0
fi

echo "[download-python-win-arm64] Downloading Python ${PY_VERSION} for Windows ARM64..."

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

curl -fSL --retry 3 "$BASE_URL/$FILENAME" -o "$WORK_DIR/cpython-win-arm64.tar.gz"

echo "[download-python-win-arm64] Extracting..."
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"
tar -xzf "$WORK_DIR/cpython-win-arm64.tar.gz" -C "$OUT_DIR" --strip-components=1

# ── Verify ────────────────────────────────────────────────────────────────────
# python.exe is a Windows PE binary — only verify the file exists, not execution.
PY_EXE="$OUT_DIR/python.exe"
if [[ ! -f "$PY_EXE" ]]; then
    echo "[download-python-win-arm64] ERROR: python.exe not found after extraction."
    echo "  Contents of $OUT_DIR:"
    ls -la "$OUT_DIR" | head -20
    exit 1
fi
echo "[download-python-win-arm64] Found: $PY_EXE"

# ── Write version stamp ───────────────────────────────────────────────────────
echo "$TARGET_VERSION" > "$VERSION_FILE"
echo "[download-python-win-arm64] Done. Windows ARM64 Python runtime ready at $OUT_DIR"
