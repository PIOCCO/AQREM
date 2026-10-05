#!/usr/bin/env bash
# AQREM — single-port web UI + API (production build served by FastAPI)
# Default port 4173 so Docker/API on 8000 can stay running.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

port_in_use() {
  local p="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -tln 2>/dev/null | grep -q ":${p} "
    return $?
  fi
  if command -v nc >/dev/null 2>&1; then
    nc -z 127.0.0.1 "$p" 2>/dev/null
    return $?
  fi
  return 1
}

pick_port() {
  local requested="$1"
  if ! port_in_use "$requested"; then
    echo "$requested"
    return
  fi
  echo "WARNING: port ${requested} is already in use." >&2
  for alt in 4173 8000 8080 3000; do
    if [[ "$alt" == "$requested" ]]; then
      continue
    fi
    if ! port_in_use "$alt"; then
      echo "WARNING: using free port ${alt} instead." >&2
      echo "$alt"
      return
    fi
  done
  echo "ERROR: no free port (tried ${requested} and 4173, 8000, 8080, 3000)." >&2
  echo "Stop the other process or set AQREM_WEB_PORT=<port> ./scripts/start-web-one-port.sh" >&2
  exit 1
}

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

HOST="${AQREM_WEB_HOST:-${API_HOST:-0.0.0.0}}"
# Lab default 4173 (Tailscale-friendly). Override: AQREM_WEB_PORT=8080 ./scripts/...
REQUESTED_PORT="${AQREM_WEB_PORT:-4173}"
PORT="$(pick_port "$REQUESTED_PORT")"

TS_IP=""
if command -v tailscale >/dev/null 2>&1; then
  TS_IP="$(tailscale ip -4 2>/dev/null | head -n1 || true)"
fi

echo "=============================================="
echo "  AQREM — http://127.0.0.1:${PORT}"
if [[ -n "$TS_IP" ]]; then
  echo "  Tailscale — http://${TS_IP}:${PORT}"
fi
echo "  Bind: ${HOST}:${PORT} (UI + API, SERVE_FRONTEND=1)"
echo "  Docker API on :8000 can stay up; this lab uses :${PORT}."
echo "  Leave this terminal OPEN. Ctrl+C to stop."
echo "=============================================="

export SERVE_FRONTEND=1
exec "$UV" app.main:app --host "$HOST" --port "$PORT"
