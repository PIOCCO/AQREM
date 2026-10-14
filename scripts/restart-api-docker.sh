#!/usr/bin/env bash
# Restart the compose "api" service on :8000 (typical Azelos / piocco setup).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found." >&2
  exit 1
fi

if [[ ! -f docker-compose.yml ]]; then
  echo "No docker-compose.yml in ${ROOT}" >&2
  exit 1
fi

COMPOSE=(docker compose)
if ! "${COMPOSE[@]}" ps --status running api >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
fi

echo "Recreating api container (backend/ is volume-mounted; no image rebuild required for route changes)..."
"${COMPOSE[@]}" up -d --force-recreate api

echo "Waiting for API..."
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:8000/api/v1/meta/api-capabilities" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

bash "${ROOT}/scripts/check-admin-delete-api.sh" "http://127.0.0.1:8000"
