#!/usr/bin/env bash
# One-time (idempotent) switch of the Pi / local Compose database to least-privilege roles.
#   1. put AQREM_MIGRATOR_DB_PASSWORD, AQREM_APP_DB_PASSWORD, AQREM_TENANT_DB_PASSWORD in .env
#      (URL-safe, e.g. `openssl rand -hex 24`)
#   2. ./scripts/pi-db-least-privilege.sh          (postgres container must be running)
#   3. docker compose -f docker-compose.local-prod.yml up -d --force-recreate api worker worker-beat
# Non-destructive: creates roles, transfers table ownership from "aqrem" to aqrem_migrator, grants DML.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COMPOSE="docker compose -f docker-compose.local-prod.yml"
# shellcheck disable=SC1091
set -a; [ -f .env ] && . ./.env; set +a
for v in AQREM_MIGRATOR_DB_PASSWORD AQREM_APP_DB_PASSWORD AQREM_TENANT_DB_PASSWORD; do
  [ -n "${!v:-}" ] || { echo "Missing $v in .env (use: openssl rand -hex 24)" >&2; exit 1; }
  [[ "${!v}" =~ ^[A-Za-z0-9_.~-]+$ ]] || { echo "$v must be URL-safe (letters, digits, _ . ~ -)" >&2; exit 1; }
done
DB="${POSTGRES_DB:-aqrem}"
echo "Taking a safety dump first (the script itself changes no data)..."
$COMPOSE exec -T postgres pg_dump -U aqrem -d "$DB" -Fc > "aqrem-before-least-privilege-$(date +%Y%m%d%H%M%S).dump"
$COMPOSE exec -T postgres psql -U aqrem -d "$DB" -v ON_ERROR_STOP=1 -v dbname="$DB" \
  -v migrator_password="$AQREM_MIGRATOR_DB_PASSWORD" -v app_password="$AQREM_APP_DB_PASSWORD" \
  -v tenant_password="$AQREM_TENANT_DB_PASSWORD" -f - < scripts/sql/least-privilege-roles.sql
echo "Done. Now recreate api/worker/worker-beat so they connect as aqrem_app / aqrem_tenant."
