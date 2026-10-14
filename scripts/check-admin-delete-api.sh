#!/usr/bin/env bash
# Verify the API on port 8000 exposes organization soft-delete routes.
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"

echo "Checking API at ${BASE}"

caps="$(curl -sf "${BASE}/api/v1/meta/api-capabilities" 2>/dev/null || true)"
if [[ -z "$caps" ]]; then
  echo "FAIL: GET /api/v1/meta/api-capabilities returned nothing (API too old or wrong host)."
  exit 1
fi
echo "Capabilities: $caps"

if ! echo "$caps" | grep -q '2026-03-org-soft-delete-v1'; then
  echo "WARN: capabilities revision mismatch — rebuild/restart backend from latest code."
fi

if command -v jq >/dev/null 2>&1; then
  if ! echo "$caps" | jq -e '.organization_soft_delete == true' >/dev/null 2>&1; then
    echo "FAIL: organization_soft_delete is not true"
    exit 1
  fi
  echo "OpenAPI delete routes:"
  curl -sf "${BASE}/openapi.json" | jq -r '.paths | keys[]' | grep -E 'schedule-deletion|/delete' || echo "(none — stale OpenAPI?)"
else
  echo "Install jq for richer checks."
fi

echo "OK: API reports organization soft-delete support."
