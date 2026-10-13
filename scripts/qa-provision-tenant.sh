#!/usr/bin/env bash
# Provisions a QA tenant for local E2E (development only). Writes frontend/e2e/.qa-credentials.json
set -euo pipefail
API="${AQREM_API:-http://127.0.0.1:8000}"
PLATFORM_EMAIL="${QA_PLATFORM_EMAIL:-qa-platform@audit.example}"
PLATFORM_PASSWORD="${QA_PLATFORM_PASSWORD:-QaAudit-Platform-12!}"
EMPLOYEE_EMAIL="${QA_EMPLOYEE_EMAIL:-qa-employee@audit.example}"
EMPLOYEE_PASSWORD="${QA_EMPLOYEE_PASSWORD:-QaEmployee-12!}"
OUT="${1:-frontend/e2e/.qa-credentials.json}"

login() {
  local email=$1 pass=$2
  curl -sf -X POST "$API/api/v1/auth/login" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$email\",\"password\":\"$pass\"}"
}

PTOKEN=$(login "$PLATFORM_EMAIL" "$PLATFORM_PASSWORD" | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

ORG_JSON=$(curl -sf -X POST "$API/api/v1/admin/organizations" \
  -H "Authorization: Bearer $PTOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"QA Audit Tenant","license_limit":5,"environment":"test"}')
ORG_ID=$(echo "$ORG_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

PROV=$(curl -sf -X POST "$API/api/v1/admin/organizations/$ORG_ID/users" \
  -H "Authorization: Bearer $PTOKEN" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMPLOYEE_EMAIL\",\"full_name\":\"QA Employee\",\"role\":\"EDITOR\"}")
SETUP=$(echo "$PROV" | python3 -c "import json,sys; print(json.load(sys.stdin)['invitation_setup_path'])")
INVITE_TOKEN=$(python3 - <<PY
from urllib.parse import urlparse, parse_qs
p = "$SETUP"
q = parse_qs(urlparse(p).query)
print(q.get("token", [""])[0])
PY
)

curl -sf -X POST "$API/api/v1/auth/accept-invitation" -H 'Content-Type: application/json' \
  -d "{\"token\":\"$INVITE_TOKEN\",\"password\":\"$EMPLOYEE_PASSWORD\",\"full_name\":\"QA Employee\"}" >/dev/null

EMP=$(login "$EMPLOYEE_EMAIL" "$EMPLOYEE_PASSWORD")
EMP_TOKEN=$(echo "$EMP" | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
EMP_ORG=$(echo "$EMP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('organization_id') or '')")

mkdir -p "$(dirname "$OUT")"
python3 - <<PY
import json
json.dump({
  "api": "$API",
  "platform_email": "$PLATFORM_EMAIL",
  "employee_email": "$EMPLOYEE_EMAIL",
  "employee_password": "$EMPLOYEE_PASSWORD",
  "employee_token": "$EMP_TOKEN",
  "organization_id": "$EMP_ORG",
  "org_id": "$ORG_ID",
}, open("$OUT", "w"), indent=2)
print("Wrote", "$OUT")
PY
