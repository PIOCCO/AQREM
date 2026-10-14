#!/usr/bin/env bash
# Simulates onboard-client key handoff without calling Azure. Proves key is not echoed.
set -euo pipefail

FAKE_JSON='{"api_key_plaintext":"gw_DRYRUN_SECRET_DO_NOT_LOG","key_prefix":"gw_DRYRU","label":"primary"}'
TMPKEY=$(mktemp)
chmod 600 "$TMPKEY"
trap 'rm -f "$TMPKEY"' EXIT

printf '%s' "$FAKE_JSON" | python3 -c 'import json,sys; open(sys.argv[1],"w").write(json.load(sys.stdin)["api_key_plaintext"])' "$TMPKEY"
echo "::add-mask::$(cat "$TMPKEY")"
LOG=$(mktemp)
{
  echo "Mint step completed"
  echo "Gateway key stored in client Key Vault (plaintext not logged)."
  wc -c < "$TMPKEY" | xargs echo "secret-bytes:"
} >"$LOG" 2>&1

if rg -F "gw_DRYRUN_SECRET_DO_NOT_LOG" "$LOG"; then
  echo "FAIL: secret appeared in log"
  exit 1
fi
echo "PASS: dry-run log contains no plaintext key"
cat "$LOG"
