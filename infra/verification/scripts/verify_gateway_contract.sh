#!/usr/bin/env bash
# Quick gateway contract check (no secrets printed). Requires curl and jq.
set -euo pipefail

GATEWAY_URL="${GATEWAY_URL:?Set GATEWAY_URL}"
GATEWAY_API_KEY="${GATEWAY_API_KEY:?Set GATEWAY_API_KEY}"

pass() { echo "PASS  $1"; }
fail() { echo "FAIL  $1"; exit 1; }

base="${GATEWAY_URL%/}"

code="$(curl -sS -o /dev/null -w '%{http_code}' "${base}/health/live")"
[[ "$code" == "200" ]] && pass health_live || fail "health_live status=$code"

embed_code="$(curl -sS -o /tmp/gw_embed.json -w '%{http_code}' \
  -H "Authorization: Bearer ${GATEWAY_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"input":["probe"]}' \
  "${base}/v1/embeddings-default/embeddings")"
[[ "$embed_code" == "200" ]] && pass embeddings || fail "embeddings status=$embed_code"

chat_code="$(curl -sS -o /tmp/gw_chat.json -w '%{http_code}' \
  -H "Authorization: Bearer ${GATEWAY_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Say OK"}],"max_tokens":8}' \
  "${base}/v1/chat-default/chat/completions")"
[[ "$chat_code" == "200" ]] && pass chat || fail "chat status=$chat_code"

bad_code="$(curl -sS -o /dev/null -w '%{http_code}' \
  -H "Authorization: Bearer invalid-key-on-purpose" \
  -H "Content-Type: application/json" \
  -d '{"input":["x"]}' \
  "${base}/v1/embeddings-default/embeddings")"
[[ "$bad_code" == "401" ]] && pass wrong_key_401 || fail "expected 401 for bad key, got $bad_code"

echo "All gateway contract checks passed."
