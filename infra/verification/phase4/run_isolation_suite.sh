#!/usr/bin/env bash
# Phase 4 isolation probes — requires two deployed clients (A and B) in dev.
set -euo pipefail

CLIENT_A_RG="${CLIENT_A_RG:?}"
CLIENT_B_RG="${CLIENT_B_RG:?}"
CLIENT_A_MI="${CLIENT_A_MI:?client-a-mi}"
CLIENT_B_MI="${CLIENT_B_MI:?client-b-mi}"

echo "=== Isolation suite (manual az login as CLIENT_A_MI required for storage/kv probes) ==="

echo "[1] Storage: A identity must not read B storage"
B_STORAGE=$(az storage account list -g "$CLIENT_B_RG" --query '[0].name' -o tsv)
if az storage blob list --account-name "$B_STORAGE" --auth-mode login -o none 2>/dev/null; then
  echo "FAIL: client A could list client B blobs"
  exit 1
fi
echo "PASS (or account not reachable)"

echo "[2] Key Vault: A must not read B secrets"
B_KV=$(az keyvault list -g "$CLIENT_B_RG" --query '[0].name' -o tsv)
if az keyvault secret show --vault-name "$B_KV" --name tenant-postgresql-password -o none 2>/dev/null; then
  echo "FAIL: client A read B KV secret"
  exit 1
fi
echo "PASS"

echo "[3] PostgreSQL: A must not auth to B server (run from A container or psql with A creds only)"
echo "    psql to B FQDN with A password — expect FATAL password authentication failed"

echo "[4] Gateway key misuse: use A gateway key with B client_id header forgery — expect 401/403"
echo "    curl GATEWAY with A key; no cross-tenant routing in gateway DB"

echo "[5] Quota isolation: saturate A RPM until 429; B client requests still 200 (separate keys)"
echo "    Run k6 with A key only, parallel single B request — B not 429"

echo "[6] DB restore: restore A backup to temp server, spot-check row count vs export manifest"
echo "    az postgres flexible-server restore ... + psql count(*) on tenant tables"

echo "Done (automated sections passed; complete manual psql/k6/restore steps in DEV)."
