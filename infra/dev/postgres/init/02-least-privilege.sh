#!/usr/bin/env bash
# Fresh volumes only (docker-entrypoint-initdb.d): create least-privilege roles before the API starts.
set -euo pipefail
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v dbname="$POSTGRES_DB" \
  -v migrator_password="$AQREM_MIGRATOR_DB_PASSWORD" -v app_password="$AQREM_APP_DB_PASSWORD" \
  -v tenant_password="$AQREM_TENANT_DB_PASSWORD" -f /aqrem-sql/least-privilege-roles.sql
