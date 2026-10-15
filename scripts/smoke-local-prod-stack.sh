#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export COMPOSE_FILE=docker-compose.local-prod.yml

echo "=== Gateway contract ==="
GATEWAY_URL=http://127.0.0.1:8088 GATEWAY_API_KEY=local_dev_gateway_key_00000001 \
  ./infra/verification/scripts/verify_gateway_contract.sh

echo "=== Model integration (in API container) ==="
docker compose exec -T api env LLM_PROVIDER=gateway \
  GATEWAY_URL=http://model-gateway:8080 \
  GATEWAY_API_KEY=local_dev_gateway_key_00000001 \
  python /app/scripts/verify_model_integration.py

echo "=== Core flow pytest ==="
docker compose exec -T api env GATEWAY_URL=http://model-gateway:8080 \
  pytest /app/tests/e2e/test_local_stack_core.py -q

echo "SMOKED PASS"
