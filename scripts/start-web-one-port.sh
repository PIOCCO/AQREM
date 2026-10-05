#!/usr/bin/env bash
# AQREM — single-port web UI + API (production build served by FastAPI)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

build_frontend() {
  echo "Building frontend (npm install + npm run build)…"
  if ! command -v npm >/dev/null 2>&1; then
    echo "ERROR: npm is not installed. Install Node 20+ and retry."
    exit 1
  fi
  (cd "$FRONTEND" && npm install && npm run build)
}

if [[ ! -f "$FRONTEND/dist/index.html" ]]; then
  build_frontend
fi

if [[ ! -f "$FRONTEND/dist/index.html" ]]; then
  echo "ERROR: frontend/dist/index.html still missing after build."
  exit 1
fi

if [[ ! -f "$BACKEND/.env" ]]; then
  if [[ -f "$ROOT/.env.example" ]]; then
    cp "$ROOT/.env.example" "$BACKEND/.env"
    echo "Created $BACKEND/.env from $ROOT/.env.example (review before production use)."
  else
    echo "ERROR: missing $BACKEND/.env — copy from $ROOT/.env.example"
    exit 1
  fi
fi

cd "$BACKEND"

if [[ ! -d ".venv" ]]; then
  echo "Creating Python virtualenv in $BACKEND/.venv …"
  python3 -m venv .venv
  .venv/bin/pip install -q -e ".[dev]"
fi

UV=".venv/bin/uvicorn"
if [[ ! -x "$UV" ]]; then
  .venv/bin/pip install -q -e ".[dev]"
fi
[[ -x "$UV" ]] || UV=uvicorn

HOST="${API_HOST:-0.0.0.0}"
PORT="${API_PORT:-8000}"

echo "=============================================="
echo "  AQREM — http://127.0.0.1:${PORT}"
echo "  (also http://0.0.0.0:${PORT} on this host)"
echo "  UI + API on one port (SERVE_FRONTEND=1)"
echo "  Leave this terminal OPEN while you browse."
echo "  Press Ctrl+C to stop."
echo "=============================================="

export SERVE_FRONTEND=1
exec "$UV" app.main:app --host "$HOST" --port "$PORT"
