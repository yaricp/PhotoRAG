#!/usr/bin/env bash
# download-python.sh — Download python-build-standalone for macOS and create a
# universal (arm64 + x86_64) build at frontend/resources/python/.
#
# Idempotent: skips the download if the version file matches the target release.
# Run from the project root.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="$PROJECT_ROOT/frontend/resources/python"
VERSION_FILE="$OUT_DIR/.python_version"

# ── Release pin ──────────────────────────────────────────────────────────────
RELEASE_TAG="20260510"
PY_VERSION="3.13.13"
BASE_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${RELEASE_TAG}"
ARM64_TAR="cpython-${PY_VERSION}+${RELEASE_TAG}-aarch64-apple-darwin-install_only.tar.gz"
X86_TAR="cpython-${PY_VERSION}+${RELEASE_TAG}-x86_64-apple-darwin-install_only.tar.gz"

TARGET_VERSION="${PY_VERSION}+${RELEASE_TAG}"

# ── Idempotency check ─────────────────────────────────────────────────────────
if [[ -f "$VERSION_FILE" ]] && [[ "$(cat "$VERSION_FILE")" == "$TARGET_VERSION" ]]; then
    echo "[download-python] Already at $TARGET_VERSION — skipping."
    exit 0
fi

echo "[download-python] Downloading Python $TARGET_VERSION for macOS universal..."

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

# ── Download ──────────────────────────────────────────────────────────────────
echo "[download-python] Fetching arm64..."
curl -fSL "$BASE_URL/$ARM64_TAR" -o "$WORK_DIR/arm64.tar.gz"

echo "[download-python] Fetching x86_64..."
curl -fSL "$BASE_URL/$X86_TAR" -o "$WORK_DIR/x86_64.tar.gz"

# ── Extract ───────────────────────────────────────────────────────────────────
echo "[download-python] Extracting..."
mkdir -p "$WORK_DIR/arm64" "$WORK_DIR/x86_64"
tar -xzf "$WORK_DIR/arm64.tar.gz" -C "$WORK_DIR/arm64" --strip-components=1
tar -xzf "$WORK_DIR/x86_64.tar.gz" -C "$WORK_DIR/x86_64" --strip-components=1

# ── Build universal output directory ─────────────────────────────────────────
# Start with the arm64 tree as the base (pure-Python files are arch-agnostic)
rm -rf "$OUT_DIR"
cp -R "$WORK_DIR/arm64/." "$OUT_DIR"

# ── Create universal binary for python3 executable ───────────────────────────
echo "[download-python] Creating universal python3 binary with lipo..."
ARM_PY="$WORK_DIR/arm64/bin/python3"
X86_PY="$WORK_DIR/x86_64/bin/python3"

if [[ -f "$ARM_PY" ]] && [[ -f "$X86_PY" ]]; then
    lipo -create -output "$OUT_DIR/bin/python3" "$ARM_PY" "$X86_PY"
else
    echo "[download-python] WARNING: python3 binary not found in one of the archives."
fi

# Also lipo any other Mach-O binaries that exist in both trees
for rel_path in $(find "$WORK_DIR/arm64" -type f -perm +0111 | sed "s|$WORK_DIR/arm64/||"); do
    arm_bin="$WORK_DIR/arm64/$rel_path"
    x86_bin="$WORK_DIR/x86_64/$rel_path"
    out_bin="$OUT_DIR/$rel_path"
    if [[ -f "$x86_bin" ]] && file "$arm_bin" | grep -q "Mach-O"; then
        lipo -create -output "$out_bin" "$arm_bin" "$x86_bin" 2>/dev/null || true
    fi
done

# ── Remove quarantine ─────────────────────────────────────────────────────────
echo "[download-python] Removing quarantine attributes..."
xattr -dr com.apple.quarantine "$OUT_DIR" 2>/dev/null || true

# ── Verify ────────────────────────────────────────────────────────────────────
echo "[download-python] Verifying..."
PY="$OUT_DIR/bin/python3"

lipo -info "$PY" | grep -E "arm64|x86_64" \
    || { echo "[download-python] ERROR: universal binary check failed"; exit 1; }

"$PY" --version \
    || { echo "[download-python] ERROR: python3 --version failed"; exit 1; }

"$PY" -m ensurepip --version 2>/dev/null \
    || echo "[download-python] WARNING: ensurepip not available (install_only should include it)"

# ── Write version stamp ───────────────────────────────────────────────────────
echo "$TARGET_VERSION" > "$VERSION_FILE"
echo "[download-python] Done. Python $TARGET_VERSION universal binary ready at $OUT_DIR"
