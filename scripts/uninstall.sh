#!/usr/bin/env bash
# uninstall.sh — fully remove PhotoRAG from this Mac.
#
# Removes:
#   /Applications/PhotoRAG.app
#   ~/Library/Application Support/PhotoRAG/   (DB, venv, AI models)
#   ~/Library/Logs/PhotoRAG/
#   ~/Library/Saved Application State/com.photorag.app.savedState/
#
# Your original photos are NOT touched.
#
# Usage:
#   bash scripts/uninstall.sh

set -euo pipefail

APP_NAME="PhotoRAG"
APP_BUNDLE="/Applications/${APP_NAME}.app"
APP_ID="com.photorag.app"
DATA_DIR="$HOME/Library/Application Support/${APP_NAME}"
LOGS_DIR="$HOME/Library/Logs/${APP_NAME}"
SAVED_STATE_DIR="$HOME/Library/Saved Application State/${APP_ID}.savedState"

RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

echo ""
echo -e "${BOLD}PhotoRAG Uninstaller${RESET}"
echo "────────────────────────────────────────"
echo "The following will be permanently deleted:"
echo ""

for path in "$APP_BUNDLE" "$DATA_DIR" "$LOGS_DIR" "$SAVED_STATE_DIR"; do
    if [[ -e "$path" ]]; then
        echo "  ✓  $path"
    else
        echo "      $path  (not found, skip)"
    fi
done

echo ""
echo -e "${RED}${BOLD}Your original photos are NOT affected.${RESET}"
echo ""
read -r -p "Continue? [y/N] " answer
if [[ ! "$answer" =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""

# Kill running instance
if pgrep -x "${APP_NAME}" >/dev/null 2>&1; then
    echo "[uninstall] Quitting ${APP_NAME}..."
    osascript -e "tell application \"${APP_NAME}\" to quit" 2>/dev/null || true
    sleep 1
fi

remove() {
    local path="$1"
    if [[ -e "$path" ]]; then
        rm -rf "$path"
        echo "[uninstall] Removed: $path"
    fi
}

remove "$APP_BUNDLE"
remove "$DATA_DIR"
remove "$LOGS_DIR"
remove "$SAVED_STATE_DIR"

# Remove preferences plist written by NSUserDefaults / Electron
defaults delete "$APP_ID" 2>/dev/null && \
    echo "[uninstall] Removed preferences: $APP_ID" || true

echo ""
echo "[uninstall] Done. PhotoRAG has been completely removed."
