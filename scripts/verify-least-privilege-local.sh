#!/usr/bin/env bash
# Simulates an EXISTING superuser-owned AQREM database, applies the one-time least-privilege script,
# then runs the whole app flow as the least-privilege roles. Needs a local PostgreSQL with pgvector and
# a superuser URL. Creates/drops the throwaway database aqrem_lp_verify.
#   ADMIN_PG="postgresql://aqrem:aqrem@localhost:5432" ./scripts/verify-least-privilege-local.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
ADMIN_PG="${ADMIN_PG:-postgresql://aqrem:aqrem@localhost:5432}"
DB=aqrem_lp_verify
HOSTPART="${ADMIN_PG#*@}"
# Reuses AQREM_*_DB_PASSWORD when set (so running it on the Pi does not change the live roles' passwords).
MP="${AQREM_MIGRATOR_DB_PASSWORD:-$(openssl rand -hex 16)}"; AP="${AQREM_APP_DB_PASSWORD:-$(openssl rand -hex 16)}"; TP="${AQREM_TENANT_DB_PASSWORD:-$(openssl rand -hex 16)}"
export EMBEDDING_DIMENSIONS="${EMBEDDING_DIMENSIONS:-384}" LLM_PROVIDER=mock APP_ENV=development
psql -q "$ADMIN_PG/postgres" -c "DROP DATABASE IF EXISTS $DB WITH (FORCE)" -c "CREATE DATABASE $DB"
echo "== 1. legacy state: schema + data created by the superuser (like the Pi today)"
DATABASE_URL="postgresql+psycopg://${ADMIN_PG#postgresql://}/$DB" python - <<'PY'
import os, sys; sys.path.insert(0, "backend")
from sqlalchemy import create_engine, text
from app.db.control_base import ControlBase; from app.db.tenant_base import TenantBase; import app.models  # noqa
e = create_engine(os.environ["DATABASE_URL"])
with e.begin() as c:
    c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    ControlBase.metadata.create_all(c); TenantBase.metadata.create_all(c)
    c.execute(text("INSERT INTO organizations (id,name,slug,license_limit,license_status,is_active,chat_shares_enabled,chat_share_ttl_days) VALUES (gen_random_uuid(),'Legacy','legacy-org',5,'active',true,false,7)"))
print("legacy schema created by", e.url.username)
PY
echo "== 2. one-time least-privilege script (as superuser)"
psql -q "$ADMIN_PG/$DB" -v dbname=$DB -v migrator_password="$MP" -v app_password="$AP" -v tenant_password="$TP" \
  -f scripts/sql/least-privilege-roles.sql
echo "== 3. app flow as least-privilege roles only"
export MIGRATION_DATABASE_URL="postgresql+psycopg://aqrem_migrator:$MP@$HOSTPART/$DB"
export DATABASE_URL="postgresql+psycopg://aqrem_app:$AP@$HOSTPART/$DB"
export TENANT_DATABASE_URL="postgresql+psycopg://aqrem_tenant:$TP@$HOSTPART/$DB"
export RUN_MIGRATIONS_ON_STARTUP=true LOCAL_PROD_STACK=true LOCAL_UPLOAD_DIR="$(mktemp -d)"
export PLATFORM_ADMIN_EMAIL=lp-super@example.com PLATFORM_ADMIN_PASSWORD="$(openssl rand -hex 12)"
export SECRET_KEY="$(openssl rand -hex 32)" AZURE_STORAGE_CONNECTION_STRING=""
set +e; python scripts/verify_least_privilege_flow.py; rc=$?; set -e
psql -q "$ADMIN_PG/$DB" -Atc "SELECT 'legacy org still present: ' || count(*) FROM organizations WHERE slug='legacy-org'"
[ "${KEEP_DB:-0}" = 1 ] || psql -q "$ADMIN_PG/postgres" -c "DROP DATABASE IF EXISTS $DB WITH (FORCE)"
exit $rc
