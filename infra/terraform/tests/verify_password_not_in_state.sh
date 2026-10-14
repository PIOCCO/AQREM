#!/usr/bin/env bash
# After terraform apply (test/dev only), prove tenant DB password is not persisted in state/plan.
set -euo pipefail

STATE="${1:?usage: verify_password_not_in_state.sh path/to/terraform.tfstate [probe-substring]}"
PROBE="${2:-}"

if [[ ! -f "$STATE" ]]; then
  echo "State file not found: $STATE" >&2
  exit 1
fi

# Ephemeral random_password must not be persisted in state at all.
if rg -q 'ephemeral\.random_password\.tenant_db|random_password\.tenant_db' "$STATE"; then
  echo "FAIL: random_password resource present in state (use ephemeral random_password)" >&2
  exit 1
fi

if rg -q '"administrator_password":' "$STATE"; then
  echo "FAIL: administrator_password (non write-only) found in state" >&2
  exit 1
fi

if [[ -n "$PROBE" ]] && rg -F "$PROBE" "$STATE"; then
  echo "FAIL: probe password string found in state" >&2
  exit 1
fi

echo "OK: no cleartext tenant password detected in $STATE"
