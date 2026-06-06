#!/usr/bin/env bash
# make-icns.sh — Generate icon.icns from a 1024×1024 source PNG.
# Run from the project root:
#   bash scripts/make-icns.sh
#
# Requires: macOS (uses sips + iconutil, both pre-installed).
# Input:    frontend/resources/icon-source.png  (1024×1024, RGBA/RGB PNG)
# Output:   frontend/resources/icon.icns

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESOURCES="$SCRIPT_DIR/../frontend/resources"
SRC="$RESOURCES/icon-source.png"
ICONSET="$RESOURCES/MyIcon.iconset"
OUT="$RESOURCES/icon.icns"

if [[ ! -f "$SRC" ]]; then
    echo "ERROR: Source image not found: $SRC"
    echo "Please place a 1024×1024 PNG at frontend/resources/icon-source.png"
    exit 1
fi

rm -rf "$ICONSET"
mkdir -p "$ICONSET"

echo "Generating icon sizes from $SRC …"

sips -z 16   16   "$SRC" --out "$ICONSET/icon_16x16.png"        > /dev/null
sips -z 32   32   "$SRC" --out "$ICONSET/icon_16x16@2x.png"     > /dev/null
sips -z 32   32   "$SRC" --out "$ICONSET/icon_32x32.png"        > /dev/null
sips -z 64   64   "$SRC" --out "$ICONSET/icon_32x32@2x.png"     > /dev/null
sips -z 128  128  "$SRC" --out "$ICONSET/icon_128x128.png"      > /dev/null
sips -z 256  256  "$SRC" --out "$ICONSET/icon_128x128@2x.png"   > /dev/null
sips -z 256  256  "$SRC" --out "$ICONSET/icon_256x256.png"      > /dev/null
sips -z 512  512  "$SRC" --out "$ICONSET/icon_256x256@2x.png"   > /dev/null
sips -z 512  512  "$SRC" --out "$ICONSET/icon_512x512.png"      > /dev/null
sips -z 1024 1024 "$SRC" --out "$ICONSET/icon_512x512@2x.png"   > /dev/null

echo "Converting iconset → .icns …"
iconutil -c icns "$ICONSET" -o "$OUT"

rm -rf "$ICONSET"

echo "Done: $OUT"
