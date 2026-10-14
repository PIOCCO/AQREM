#!/usr/bin/env bash
# Stop anything listening on :8000 and start uvicorn from backend/ on all interfaces
# (required when the UI uses a Tailscale/LAN IP like 100.x.x.x:5173 → :8000).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="${ROOT}/backend"
HOST="${API_HOST:-0.0.0.0}"
PORT="${API_PORT:-8000}"

if [[ ! -d "${BACKEND}/.venv" ]]; then
  echo "Missing ${BACKEND}/.venv — run install from repo root first." >&2
  exit 1
fi

echo "Stopping listeners on port ${PORT}..."
if command -v fuser >/dev/null 2>&1; then
  fuser -k "${PORT}/tcp" 2>/dev/null || true
else
  pids="$(ss -tlnp 2>/dev/null | awk -v p=":${PORT}" '$4 ~ p { print $0 }' || true)"
  if [[ -n "${pids}" ]]; then
    echo "Port ${PORT} in use (install fuser or stop uvicorn manually):" >&2
    echo "${pids}" >&2
    exit 1
  fi
fi
sleep 0.5

cd "${BACKEND}"
export PYTHONPATH="${BACKEND}"
echo "Starting uvicorn on ${HOST}:${PORT} (factory app, reload)..."
exec .venv/bin/uvicorn app.main:create_app --factory --host "${HOST}" --port "${PORT}" --reload
