#!/usr/bin/env bash
# AQREM end-to-end verification helper (local machine with Docker).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Checking Docker..."
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found. Install Docker to run full integration tests."
  exit 1
fi

echo "==> Starting Postgres, Redis, Azurite..."
docker compose up -d postgres redis azurite
docker compose exec postgres psql -U aqrem -tc "SELECT 1 FROM pg_database WHERE datname='aqrem_test'" | grep -q 1 \
  || docker compose exec postgres psql -U aqrem -c "CREATE DATABASE aqrem_test;"

echo "==> Backend unit + integration tests..."
pip install -e backend[dev] -q
export TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql+psycopg://aqrem:aqrem@localhost:5432/aqrem_test}"
python3 -m pytest tests/backend -q

echo "==> Frontend build + tests..."
(cd frontend && npm ci && npm run test && npm run build)

echo "==> API health (requires api service)..."
if curl -sf http://127.0.0.1:8000/health/live >/dev/null 2>&1; then
  curl -s http://127.0.0.1:8000/health/ready | python3 -m json.tool
else
  echo "SKIP: API not running on :8000 (start with: docker compose up --build api worker)"
fi

if [[ "${RUN_AZURE_SMOKE:-}" == "1" ]]; then
  echo "==> Azure OpenAI smoke test..."
  python3 scripts/azure_openai_smoke.py
else
  echo "SKIP: Azure smoke (set RUN_AZURE_SMOKE=1 and LLM_PROVIDER=azure with credentials)"
fi

echo "==> E2E verification script finished."
