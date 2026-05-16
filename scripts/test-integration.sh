#!/usr/bin/env bash
# test-integration.sh — Smoke-test the packaged Python backend.
#
# Simulates what the setup wizard does at first launch:
#   1. Creates a venv using the bundled Python
#   2. pip-installs backend/requirements.txt into it
#   3. Spawns the backend via the venv Python
#   4. Polls /api/system/status/ for up to 60 s
#   5. Asserts HTTP 200 and that db.sqlite3 was created
#
# Usage (from project root):
#   bash scripts/test-integration.sh [path/to/dist-electron]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="${1:-$PROJECT_ROOT/frontend/dist-electron}"

# ── Locate the .app ──────────────────────────────────────────────────────────
APP_PATH="$(find "$DIST_DIR" -maxdepth 2 -name "*.app" -type d | head -1)"
if [[ -z "$APP_PATH" ]]; then
    echo "ERROR: No .app bundle found in $DIST_DIR"
    exit 1
fi
echo "[integration] Testing: $APP_PATH"

RESOURCES="$APP_PATH/Contents/Resources"
BUNDLED_PYTHON="$RESOURCES/python/bin/python3"
BACKEND="$RESOURCES/backend"

# ── Temp workspace (acts as APP_DATA_DIR) ────────────────────────────────────
TMP_DATA="$(mktemp -d)"
VENV="$TMP_DATA/venv"

cleanup() {
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
    rm -rf "$TMP_DATA"
}
trap cleanup EXIT

# ── Step 1: create venv using bundled Python ─────────────────────────────────
echo "[integration] Creating venv with bundled Python…"
"$BUNDLED_PYTHON" -m venv "$VENV"
VENV_PYTHON="$VENV/bin/python3"
VENV_PIP="$VENV/bin/pip"

# ── Step 2: install backend requirements ─────────────────────────────────────
echo "[integration] Installing requirements (this may take a few minutes)…"
"$VENV_PIP" install -r "$BACKEND/requirements.txt" --quiet --progress-bar off

# ── Pick a free port ─────────────────────────────────────────────────────────
PORT=$(python3 -c "import socket; s=socket.socket(); s.bind(('',0)); print(s.getsockname()[1]); s.close()")
echo "[integration] APP_DATA_DIR=$TMP_DATA  PORT=$PORT"

# ── Step 3: spawn the backend via the venv Python ────────────────────────────
APP_DATA_DIR="$TMP_DATA" \
API_PORT="$PORT" \
QUEUE_DB_DIR="$TMP_DATA" \
HUGGINGFACE_HUB_CACHE="$TMP_DATA/.hf_cache" \
    "$VENV_PYTHON" "$BACKEND/run.py" > "$TMP_DATA/backend.log" 2>&1 &
BACKEND_PID=$!

# ── Step 4: poll for up to 60 s ──────────────────────────────────────────────
echo "[integration] Waiting for backend on port $PORT…"
READY=0
for i in $(seq 1 120); do
    if curl -sf "http://127.0.0.1:$PORT/api/system/status/" > /dev/null 2>&1; then
        echo "[integration] Backend ready after $(echo "scale=1; $i / 2" | bc) s"
        READY=1
        break
    fi
    sleep 0.5
done

if [[ $READY -eq 0 ]]; then
    echo "ERROR: Backend did not start within 60 s"
    echo "--- backend log (last 40 lines) ---"
    tail -40 "$TMP_DATA/backend.log" || true
    exit 1
fi

# ── Step 5: assert HTTP 200 ───────────────────────────────────────────────────
STATUS=$(curl -so /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/api/system/status/")
if [[ "$STATUS" != "200" ]]; then
    echo "ERROR: Expected HTTP 200, got $STATUS"
    exit 1
fi
echo "[integration] ✓ GET /api/system/status/ → 200"

# ── Assert db.sqlite3 was created ────────────────────────────────────────────
kill "$BACKEND_PID" 2>/dev/null || true
wait "$BACKEND_PID" 2>/dev/null || true

if [[ ! -f "$TMP_DATA/db.sqlite3" ]]; then
    echo "ERROR: db.sqlite3 not found in APP_DATA_DIR"
    echo "--- backend log (last 40 lines) ---"
    tail -40 "$TMP_DATA/backend.log" || true
    exit 1
fi
echo "[integration] ✓ db.sqlite3 created in APP_DATA_DIR"

echo ""
echo "[integration] All smoke tests passed."
