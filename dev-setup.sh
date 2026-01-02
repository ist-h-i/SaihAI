#!/usr/bin/env bash
set -euo pipefail

pause_on_error() {
  echo
  echo "Press any key to close..."
  read -n 1 -s -r
  exit 1
}

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== SaihAI dev setup (one-time) ==="
echo "Repo: \"$ROOT\""
echo

if ! command -v uv >/dev/null 2>&1; then
  echo "[ERROR] \"uv\" not found in PATH."
  echo "Install uv: https://docs.astral.sh/uv/"
  pause_on_error
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[ERROR] \"npm\" not found in PATH."
  echo "Install Node.js (includes npm): https://nodejs.org/"
  pause_on_error
fi

echo "[backend] uv sync"
if [ ! -d "$ROOT/backend" ]; then
  echo "[ERROR] backend directory not found: \"$ROOT/backend\""
  pause_on_error
fi
pushd "$ROOT/backend" >/dev/null
if ! uv sync; then
  popd >/dev/null
  echo "[ERROR] backend setup failed (uv sync)."
  pause_on_error
fi
popd >/dev/null

echo "[frontend] npm ci"
if [ ! -d "$ROOT/frontend" ]; then
  echo "[ERROR] frontend directory not found: \"$ROOT/frontend\""
  pause_on_error
fi
pushd "$ROOT/frontend" >/dev/null
if ! npm ci; then
  popd >/dev/null
  echo "[ERROR] frontend setup failed (npm ci)."
  echo "If this is a dev machine, you can try: npm install"
  pause_on_error
fi
popd >/dev/null

echo
echo "Setup complete."
echo "Next: run dev-start.sh"
exit 0
