#!/usr/bin/env bash
# test-integration.sh — Smoke-test the packaged Python backend.
#
# Finds the first .app in frontend/dist-electron/, spawns the bundled
# Python backend, polls /api/system/status/ for 30 s, asserts HTTP 200,
# then kills the backend and checks that db.sqlite3 was created.
#
# Usage:
#   bash scripts/test-integration.sh [path/to/dist-electron]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="${1:-$PROJECT_ROOT/frontend/dist-electron}"

# Locate the .app
APP_PATH="$(find "$DIST_DIR" -maxdepth 2 -name "*.app" -type d | head -1)"
if [[ -z "$APP_PATH" ]]; then
    echo "ERROR: No .app bundle found in $DIST_DIR"
    exit 1
fi
echo "[integration] Testing: $APP_PATH"

# Resources paths inside the bundle
RESOURCES="$APP_PATH/Contents/Resources"
PYTHON="$RESOURCES/python/bin/python3"
BACKEND="$RESOURCES/backend"

# Temp data directory — must be set before spawning the backend
TMP_DATA="$(mktemp -d)"

# Pick a free port before spawning
PORT=$(python3 -c "import socket; s=socket.socket(); s.bind(('',0)); print(s.getsockname()[1]); s.close()")

echo "[integration] APP_DATA_DIR=$TMP_DATA  PORT=$PORT"

# Spawn the backend with all env vars set, running from its own directory
APP_DATA_DIR="$TMP_DATA" \
API_PORT="$PORT" \
QUEUE_DB_DIR="$TMP_DATA" \
    "$PYTHON" "$BACKEND/run.py" > "$TMP_DATA/backend.log" 2>&1 &
BACKEND_PID=$!

cleanup() {
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
    rm -rf "$TMP_DATA"
}
trap cleanup EXIT

# Wait up to 30 s for the backend to respond
echo "[integration] Waiting for backend on port $PORT …"
for i in $(seq 1 60); do
    if curl -sf "http://127.0.0.1:$PORT/api/system/status/" > /dev/null 2>&1; then
        echo "[integration] Backend responded after $(echo "scale=1; $i / 2" | bc) s"
        break
    fi
    if [[ $i -eq 60 ]]; then
        echo "ERROR: Backend did not start within 30 s"
        echo "--- backend log ---"
        cat "$TMP_DATA/backend.log" || true
        exit 1
    fi
    sleep 0.5
done

# Assert HTTP 200
STATUS=$(curl -so /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/api/system/status/")
if [[ "$STATUS" != "200" ]]; then
    echo "ERROR: Expected HTTP 200, got $STATUS"
    exit 1
fi
echo "[integration] ✓ GET /api/system/status/ → 200"

# Kill backend cleanly before checking side-effects
kill "$BACKEND_PID" 2>/dev/null || true
wait "$BACKEND_PID" 2>/dev/null || true

# Assert db.sqlite3 was created
if [[ ! -f "$TMP_DATA/db.sqlite3" ]]; then
    echo "ERROR: db.sqlite3 not found in APP_DATA_DIR"
    echo "--- backend log ---"
    cat "$TMP_DATA/backend.log" || true
    exit 1
fi
echo "[integration] ✓ db.sqlite3 created in APP_DATA_DIR"

echo ""
echo "[integration] All smoke tests passed."
