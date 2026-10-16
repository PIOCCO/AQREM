#!/usr/bin/env bash
# Roll out an image tag to one or all dedicated environments (Azure Container Apps).
#
#   scripts/rollout-dedicated.sh <image_tag> <client|all> [--registry acr.azurecr.io] [--dry-run]
#
# Per environment (resource group rg-aqrem-<client>):
#   1. update + run the <client>-migrate job with the new api image (forward-only, additive migrations)
#   2. wait for the job to succeed (aborts this env otherwise; running apps untouched)
#   3. update api, worker, beat, web to the new tag
#   4. poll https://<web>/api/v1/version until it reports the tag, then check /health
# Rollback: run the same command with the previous tag. Migrations are additive, so the previous
# image runs on the newer schema (see docs/migrations.md). Restore the DB only to discard data.
# "all" = every resource group tagged tier=dedicated in the current subscription.
# Afterwards set image_tag in platform.auto.tfvars to the same tag so a later terraform apply does not revert it.
set -euo pipefail
[[ $# -ge 2 ]] || { sed -n '2,15p' "$0"; exit 1; }
TAG="$1"; TARGET="$2"; shift 2
REGISTRY="${AQREM_REGISTRY:-}"; DRY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --registry) REGISTRY="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    *) echo "unknown arg $1" >&2; exit 1 ;;
  esac
done
[[ -n "$REGISTRY" ]] || { echo "set --registry or AQREM_REGISTRY" >&2; exit 1; }
run() { if [[ $DRY == 1 ]]; then echo "+ $*"; else "$@"; fi; }

if [[ "$TARGET" == all ]]; then
  mapfile -t CLIENTS < <(az group list --tag tier=dedicated --query "[].tags.client" -o tsv | sort -u)
else
  CLIENTS=("$TARGET")
fi
FAILED=()
for c in "${CLIENTS[@]}"; do
  rg="rg-aqrem-$c"
  echo "=== $c ($rg) -> $TAG"
  run az containerapp job update -n "$c-migrate" -g "$rg" --image "$REGISTRY/aqrem-api:$TAG" -o none
  if [[ $DRY == 0 ]]; then
    exec_name="$(az containerapp job start -n "$c-migrate" -g "$rg" --query name -o tsv)"
    for _ in $(seq 1 90); do
      st="$(az containerapp job execution show -n "$c-migrate" -g "$rg" --job-execution-name "$exec_name" --query properties.status -o tsv)"
      [[ "$st" == Succeeded || "$st" == Failed ]] && break
      sleep 10
    done
    if [[ "$st" != Succeeded ]]; then echo "migration $st for $c; skipping app update"; FAILED+=("$c"); continue; fi
  else
    run az containerapp job start -n "$c-migrate" -g "$rg"
  fi
  # One revision per app: new image + APP_VERSION (reported by /api/v1/version).
  run az containerapp update -n "$c-api" -g "$rg" --image "$REGISTRY/aqrem-api:$TAG" --set-env-vars "APP_VERSION=$TAG" -o none
  for w in worker beat; do
    run az containerapp update -n "$c-$w" -g "$rg" --image "$REGISTRY/aqrem-worker:$TAG" --set-env-vars "APP_VERSION=$TAG" -o none
  done
  run az containerapp update -n "$c-web" -g "$rg" --image "$REGISTRY/aqrem-web:$TAG" -o none
  if [[ $DRY == 0 ]]; then
    fqdn="$(az containerapp show -n "$c-web" -g "$rg" --query properties.configuration.ingress.fqdn -o tsv)"
    ok=0
    for _ in $(seq 1 30); do
      v="$(curl -fsS "https://$fqdn/api/v1/version" 2>/dev/null | python3 -c 'import json,sys;print(json.load(sys.stdin)["version"])' || true)"
      [[ "$v" == "$TAG" ]] && { ok=1; break; }
      sleep 10
    done
    curl -fsS "https://$fqdn/health" | python3 -c 'import json,sys;d=json.load(sys.stdin);print("health:",d["status"],d.get("degraded"))' || true
    [[ $ok == 1 ]] || { echo "$c did not report $TAG"; FAILED+=("$c"); }
  fi
done
if [[ ${#FAILED[@]} -gt 0 ]]; then echo "FAILED: ${FAILED[*]} (roll back with the previous tag)"; exit 1; fi
echo "Rollout of $TAG complete for: ${CLIENTS[*]}"
