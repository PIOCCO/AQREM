#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export COMPOSE_FILE=docker-compose.local-prod.yml
echo "Starting production-like local stack..."
docker compose up -d --build
echo "Waiting for API health..."
for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8000/health/live >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -sf http://127.0.0.1:8000/health/live >/dev/null || { echo "API did not become healthy"; exit 1; }
echo "Seeding model gateway key..."
docker compose exec -T postgres psql -U aqrem -d aqrem -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;" >/dev/null
docker compose run --rm -e DATABASE_URL=postgresql://aqrem:aqrem@postgres:5432/aqrem \
  -e GATEWAY_API_KEY=local_dev_gateway_key_00000001 \
  api python /app/infra/dev/seed_local_gateway.py || true
echo "Stack is up. Web: http://127.0.0.1:5173  API: http://127.0.0.1:8000  Gateway: http://127.0.0.1:8088"
