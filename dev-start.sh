#!/usr/bin/env bash
set -euo pipefail

pause_on_error() {
  echo
  echo "Press any key to close..."
  read -n 1 -s -r
  exit 1
}

port_in_use() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi
  return 1
}

run_in_terminal() {
  local workdir="$1"
  local cmd="$2"
  local script="cd \"$workdir\"; $cmd"
  local escaped=${script//\"/\\\"}
  /usr/bin/osascript -e "tell application \"Terminal\" to do script \"$escaped\"" >/dev/null
}

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== SaihAI dev start ==="
echo "Repo: \"$ROOT\""
echo

if ! command -v npm >/dev/null 2>&1; then
  echo "[ERROR] \"npm\" not found in PATH."
  echo "Run dev-setup.sh first (after installing Node.js)."
  pause_on_error
fi

BACKEND_CMD=()
if command -v uv >/dev/null 2>&1; then
  BACKEND_CMD=(uv run uvicorn app.main:app --reload)
elif command -v uvicorn >/dev/null 2>&1; then
  BACKEND_CMD=(uvicorn app.main:app --reload)
else
  echo "[ERROR] Neither \"uv\" nor \"uvicorn\" found in PATH."
  echo "Run dev-setup.sh first (and ensure uv is installed)."
  pause_on_error
fi

BACKEND_PORT="${BACKEND_PORT:-8000}"
if port_in_use "$BACKEND_PORT" && [ "$BACKEND_PORT" = "8000" ]; then
  echo "[WARN] Port $BACKEND_PORT is already in use. Switching backend port to 8001."
  BACKEND_PORT=8001
fi

FRONTEND_PORT="${FRONTEND_PORT:-4200}"
if port_in_use "$FRONTEND_PORT" && [ "$FRONTEND_PORT" = "4200" ]; then
  echo "[WARN] Port $FRONTEND_PORT is already in use. Switching frontend port to 4201."
  FRONTEND_PORT=4201
fi

if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "[WARN] frontend/node_modules not found. Run dev-setup.sh first."
fi

if [ ! -d "$ROOT/backend/.venv" ]; then
  echo "[WARN] backend/.venv not found. Run dev-setup.sh first."
fi

echo "Starting backend..."
if [ ! -d "$ROOT/backend" ]; then
  echo "[ERROR] backend directory not found: \"$ROOT/backend\""
  pause_on_error
fi

if [ "${NO_NEW_WINDOW:-}" = "1" ]; then
  (cd "$ROOT/backend" && "${BACKEND_CMD[@]}" --port "$BACKEND_PORT") &
else
  run_in_terminal "$ROOT/backend" "${BACKEND_CMD[*]} --port $BACKEND_PORT"
fi

echo "Starting frontend..."
if [ ! -d "$ROOT/frontend" ]; then
  echo "[ERROR] frontend directory not found: \"$ROOT/frontend\""
  pause_on_error
fi

if [ "${NO_NEW_WINDOW:-}" = "1" ]; then
  (cd "$ROOT/frontend" && npm run start -- --port "$FRONTEND_PORT") &
  disown -a 2>/dev/null || true
else
  run_in_terminal "$ROOT/frontend" "npm run start -- --port $FRONTEND_PORT"
fi

echo
echo "Backend:  http://localhost:$BACKEND_PORT/api/health"
echo "Frontend: http://localhost:$FRONTEND_PORT"
exit 0
