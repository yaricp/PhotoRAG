#!/usr/bin/env bash
# make-ico.sh — Generate icon.ico from a 1024×1024 source PNG.
# Run from the project root:
#   bash scripts/make-ico.sh
#
# Requires: ImageMagick (magick command).  Install via: brew install imagemagick
# Input:    frontend/resources/icon-source.png  (1024×1024 PNG)
# Output:   frontend/resources/icon.ico         (16 / 32 / 48 / 64 / 128 / 256 px)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESOURCES="$SCRIPT_DIR/../frontend/resources"
SRC="$RESOURCES/icon-source.png"
OUT="$RESOURCES/icon.ico"

if [[ ! -f "$SRC" ]]; then
    echo "ERROR: Source image not found: $SRC"
    echo "Please place a 1024×1024 PNG at frontend/resources/icon-source.png"
    exit 1
fi

if ! command -v magick &>/dev/null; then
    echo "ERROR: ImageMagick not found. Install with: brew install imagemagick"
    exit 1
fi

echo "Generating icon.ico from $SRC …"

magick "$SRC" \
    \( -clone 0 -resize 256x256 \) \
    \( -clone 0 -resize 128x128 \) \
    \( -clone 0 -resize 64x64  \) \
    \( -clone 0 -resize 48x48  \) \
    \( -clone 0 -resize 32x32  \) \
    \( -clone 0 -resize 16x16  \) \
    -delete 0 "$OUT"

echo "Done: $OUT"
magick identify "$OUT" | awk '{print "  " $2 " " $3}'
