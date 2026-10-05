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

load_dotenv_var() {
  local file="$1" key="$2"
  [[ -f "$file" ]] || return 1
  grep -E "^${key}=" "$file" 2>/dev/null | tail -n1 | cut -d= -f2- | sed 's/^["'\''"]//; s/["'\''"]$//' || true
}

parse_db_host_port() {
  local url="${1:-}"
  local host="127.0.0.1"
  local port="5432"
  if [[ -z "$url" ]]; then
    echo "$host $port"
    return
  fi
  if [[ "$url" =~ @([^:/]+):([0-9]+)/ ]]; then
    host="${BASH_REMATCH[1]}"
    port="${BASH_REMATCH[2]}"
  elif [[ "$url" =~ @([^:/]+)/ ]]; then
    host="${BASH_REMATCH[1]}"
  fi
  echo "$host $port"
}

tcp_open() {
  local host="$1" port="$2"
  if command -v nc >/dev/null 2>&1; then
    nc -z "$host" "$port" 2>/dev/null
    return $?
  fi
  if command -v timeout >/dev/null 2>&1 && command -v bash >/dev/null 2>&1; then
    timeout 1 bash -c "echo >/dev/tcp/${host}/${port}" 2>/dev/null
    return $?
  fi
  return 1
}

wait_for_tcp() {
  local host="$1" port="$2" label="$3" max="${4:-45}"
  local i=1
  while [[ "$i" -le "$max" ]]; do
    if tcp_open "$host" "$port"; then
      return 0
    fi
    sleep 1
    i=$((i + 1))
  done
  echo "ERROR: timed out waiting for ${label} at ${host}:${port} (${max}s)." >&2
  return 1
}

ensure_lab_dependencies() {
  local env_file="$BACKEND/.env"
  local db_url
  db_url="$(load_dotenv_var "$env_file" DATABASE_URL)"
  db_url="${db_url:-postgresql+psycopg://aqrem:aqrem@localhost:5432/aqrem}"
  read -r DB_HOST DB_PORT <<< "$(parse_db_host_port "$db_url")"

  if tcp_open "$DB_HOST" "$DB_PORT"; then
    return 0
  fi

  echo "PostgreSQL is not reachable at ${DB_HOST}:${DB_PORT}." >&2

  local auto_docker="${AQREM_AUTO_DOCKER:-1}"
  if [[ "$auto_docker" == "0" || "$auto_docker" == "false" || "$auto_docker" == "no" ]]; then
    print_db_help "$DB_HOST" "$DB_PORT"
    exit 1
  fi

  if [[ ! -f "$ROOT/docker-compose.yml" ]]; then
    print_db_help "$DB_HOST" "$DB_PORT"
    exit 1
  fi

  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is not installed; cannot start postgres automatically." >&2
    print_db_help "$DB_HOST" "$DB_PORT"
    exit 1
  fi

  if ! docker compose version >/dev/null 2>&1 && ! docker-compose version >/dev/null 2>&1; then
    echo "Docker Compose is not available." >&2
    print_db_help "$DB_HOST" "$DB_PORT"
    exit 1
  fi

  echo "Starting lab dependencies (postgres, redis, azurite) via Docker Compose…" >&2
  (cd "$ROOT" && docker compose up -d postgres redis azurite)

  if [[ "$DB_HOST" == "postgres" ]]; then
    echo "WARNING: DATABASE_URL uses host 'postgres' (Docker network name)." >&2
    echo "For host-run uvicorn, set in .env:" >&2
    echo "  DATABASE_URL=postgresql+psycopg://aqrem:aqrem@localhost:5432/aqrem" >&2
    DB_HOST="127.0.0.1"
  fi

  wait_for_tcp "$DB_HOST" "$DB_PORT" "PostgreSQL" 60 || exit 1
  echo "PostgreSQL is up at ${DB_HOST}:${DB_PORT}." >&2
}

print_db_help() {
  local host="$1" port="$2"
  cat >&2 <<EOF

The one-port server needs PostgreSQL before it can start (startup runs migrations).

Quick fix (from repo root):
  docker compose up -d postgres redis azurite

Then confirm port ${port} is listening:
  docker compose ps
  nc -z ${host} ${port}

Optional: run Celery worker for source sync / indexing jobs:
  docker compose up -d worker

To skip auto Docker start:
  AQREM_AUTO_DOCKER=0 ./scripts/start-web-one-port.sh

EOF
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

if [[ -f "$ROOT/.env" ]]; then
  if [[ ! -f "$BACKEND/.env" ]] || ! cmp -s "$ROOT/.env" "$BACKEND/.env" 2>/dev/null; then
    cp "$ROOT/.env" "$BACKEND/.env"
    echo "Using $ROOT/.env for backend (same SECRET_KEY as Docker Compose)."
  fi
elif [[ ! -f "$BACKEND/.env" ]]; then
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

ensure_lab_dependencies

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
