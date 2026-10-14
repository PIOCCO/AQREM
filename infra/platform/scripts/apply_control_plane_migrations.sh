#!/usr/bin/env bash
# Apply control-plane SQL as bootstrap Entra admin (psql + AAD token).
set -euo pipefail

HOST="${CP_PG_HOST:?}"
DB="${CP_PG_DATABASE:-aqrem_control}"
USER="${CP_PG_ADMIN_USER:?}"
DIR="$(cd "$(dirname "$0")/../db/migrations" && pwd)"

export PGPASSWORD="$(az account get-access-token --resource-type oss-rdbms --query accessToken -o tsv)"

for f in 001_platform_schema.sql 002_gateway_schema.sql 003_gateway_least_privilege_role.sql 004_tenant_embedding_metadata.sql 005_platform_component_roles.sql; do
  echo "Applying $f"
  psql "host=$HOST dbname=$DB user=$USER sslmode=require" -v ON_ERROR_STOP=1 -f "$DIR/$f"
done

echo "Done. Grant gateway MI: GRANT aqrem_gateway_app TO \"<gw-mi-name>\";"
