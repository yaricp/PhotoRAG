#!/usr/bin/env bash
# test-integration.sh -- Smoke-test the packaged Python backend.
#
# Simulates the setup wizard:
#   1. Create venv using bundled Python
#   2. pip-install backend/requirements.txt
#   3. Spawn backend via venv Python with a temp APP_DATA_DIR
#   4. Poll /api/system/status/ for up to 60 s
#   5. Assert HTTP 200 and that db.sqlite3 was created
#
# Usage (from project root):
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

RESOURCES="$APP_PATH/Contents/Resources"
BUNDLED_PYTHON="$RESOURCES/python/bin/python3"
BACKEND="$RESOURCES/backend"

# Temp workspace acts as APP_DATA_DIR
TMP_DATA="$(mktemp -d)"

# Initialize before trap so cleanup never references an unset variable
BACKEND_PID=""

cleanup() {
    if [[ -n "$BACKEND_PID" ]]; then
        kill "$BACKEND_PID" 2>/dev/null || true
        wait "$BACKEND_PID" 2>/dev/null || true
    fi
    rm -rf "$TMP_DATA"
}
trap cleanup EXIT

# Step 1: create venv using bundled Python
echo "[integration] Creating venv..."
"$BUNDLED_PYTHON" -m venv "$TMP_DATA/venv"
VENV_PYTHON="$TMP_DATA/venv/bin/python3"
VENV_PIP="$TMP_DATA/venv/bin/pip"

# Step 2: install backend requirements
echo "[integration] Installing requirements (this may take a few minutes)..."
"$VENV_PIP" install -r "$BACKEND/requirements.txt" --quiet --progress-bar off

# Pick a free port
PORT="$(python3 -c "import socket; s=socket.socket(); s.bind(('',0)); p=s.getsockname()[1]; s.close(); print(p)")"
echo "[integration] APP_DATA_DIR=$TMP_DATA  PORT=$PORT"

# Step 3: spawn backend with explicit env, no inline assignment
export APP_DATA_DIR="$TMP_DATA"
export API_PORT="$PORT"
export QUEUE_DB_DIR="$TMP_DATA"
export HUGGINGFACE_HUB_CACHE="$TMP_DATA/.hf_cache"

"$VENV_PYTHON" "$BACKEND/run.py" >"$TMP_DATA/backend.log" 2>&1 &
BACKEND_PID="$!"

# Step 4: poll for up to 60 s
echo "[integration] Waiting for backend on port $PORT..."
READY=0
i=0
while [[ $i -lt 120 ]]; do
    if curl -sf "http://127.0.0.1:${PORT}/api/system/status/" >/dev/null 2>&1; then
        elapsed=$(( i / 2 ))
        echo "[integration] Backend ready after ${elapsed}s"
        READY=1
        break
    fi
    sleep 0.5
    i=$(( i + 1 ))
done

if [[ "$READY" -eq 0 ]]; then
    echo "ERROR: Backend did not start within 60 s"
    echo "--- backend log (last 40 lines) ---"
    tail -40 "$TMP_DATA/backend.log" || true
    exit 1
fi

# Assert HTTP 200
HTTP_STATUS="$(curl -so /dev/null -w "%{http_code}" "http://127.0.0.1:${PORT}/api/system/status/")"
if [[ "$HTTP_STATUS" != "200" ]]; then
    echo "ERROR: Expected HTTP 200, got $HTTP_STATUS"
    exit 1
fi
echo "[integration] OK: GET /api/system/status/ -> 200"

# Stop backend before checking side-effects
kill "$BACKEND_PID" 2>/dev/null || true
wait "$BACKEND_PID" 2>/dev/null || true
BACKEND_PID=""

# Assert db.sqlite3 was created
if [[ ! -f "$TMP_DATA/db.sqlite3" ]]; then
    echo "ERROR: db.sqlite3 not found in APP_DATA_DIR"
    echo "--- backend log (last 40 lines) ---"
    tail -40 "$TMP_DATA/backend.log" || true
    exit 1
fi
echo "[integration] OK: db.sqlite3 created in APP_DATA_DIR"

echo ""
echo "[integration] All smoke tests passed."
