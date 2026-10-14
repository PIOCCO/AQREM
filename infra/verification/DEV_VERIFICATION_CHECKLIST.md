# DEV subscription verification checklist (single runbook)

Run in order. Record pass/fail. **Do not skip expected results.**

## 0. Prerequisites

- [ ] Dedicated dev subscription, `az login`, Terraform ≥ 1.11, `k6`, `docker`, `psql`, `jq`
- [ ] Platform + one client deployed (**you** run apply — not the agent)

---

## 1. Password not in state

```bash
cd infra/terraform/stacks/client
terraform apply -var-file=../../parameters/clients/acme.sample.tfvars.json   # only with your approval
PROBE="$(openssl rand -base64 24)"
# (Probe is for manual grep only if you captured password elsewhere — ephemeral passwords won't be in state)
./infra/terraform/tests/verify_password_not_in_state.sh terraform.tfstate "$PROBE"
rg -i 'administrator_password":|random_password\.tenant_db' terraform.tfstate && echo FAIL || echo OK
```

**Expected:** `OK: no cleartext tenant password detected`; `rg` finds **no** non-`_wo` password fields or `random_password.tenant_db`.

**Rotation:** bump `_wo_version` to `2`, apply again, connect with KV secret only — old password fails. See `docs/TENANT_DB_PASSWORD_ROTATION.md`.

---

## 2. k6 gateway load (realistic + 5× streaming)

```bash
cd infra/model-gateway
docker compose -f docker-compose.loadtest.yml up -d --build
# Seed gateway.client + gateway.api_key in cp-postgres (or use bootstrap SQL)
export GATEWAY_URL=http://localhost:8088 GATEWAY_API_KEY='gw_...'
K6_VUS=50  K6_DURATION=5m K6_STREAM=1 k6 run load/k6-gateway.js
K6_VUS=250 K6_DURATION=5m K6_STREAM=1 k6 run load/k6-gateway.js
```

**Expected:** p95 latency documented in `GATEWAY_LOAD_TEST.md`; 429 rate < 5% at realistic load; DB CPU stable or documented; 5× may show higher 429 — not widespread 5xx.

---

## 3. Cell concurrency (20 onboardings, 5 free slots)

```bash
export TEST_CELL_DATABASE_URL="postgresql://..."   # control-plane DB after migrations
pytest infra/platform/db/tests/test_cell_concurrency.py -m integration -vv
```

**Expected:** `successes == 5`, final `clients_used == max_clients` (10 in test fixture), **no** row with `clients_used > max_clients`.

---

## 4. Provisioning role what-ifs

As the **provisioner SP** (not Owner):

```bash
az group create -n contoso-test-rg -l westeurope                    # expect DENY (policy)
az group create -n aqrem-dev-test-rg -l westeurope                  # expect ALLOW (if naming matches)
az role assignment create --assignee $PROVISIONER_SP --role Owner --scope /subscriptions/.../resourceGroups/aqrem-dev-test-rg   # expect AuthorizationFailed
```

Touch another client's RG (replace ids):

```bash
az group delete -n aqrem-dev-otherclient-rg --yes                 # expect DENY or NotFound unless that RG is in provisioner scope and naming policy allows
```

**Expected:** Policy blocks non-prefix; Owner/UAA assignment fails; cross-client RG delete not allowed for provisioner identity.

---

## 5. Gateway outage (real control-plane DB)

Deploy gateway against real CP PG. Then block PG NSG/firewall or stop PG briefly.

| Test | Action | Expected |
|------|--------|----------|
| Known key | Call `/v1/chat-default/...` with cached key during outage (< KEY_VALIDATION_CACHE_SECONDS) | **200** (mock/upstream permitting) |
| Unknown key | New invalid key during outage | **401** |
| Revoked key | Revoke in DB, wait > KEY_REVOKE_MAX_SECONDS | **401** |
| Budget | Exhaust budget in DB before outage | **429** during outage when cache reflects budget |

Automated unit tests (local, no Azure): `pytest infra/model-gateway/tests/test_failopen.py`

---

## 6. Cross-client isolation (client A → client B assets)

Scripts: `infra/verification/phase4/run_isolation_suite.sh` (requires deployed client A and B).

**Expected:** Each probe returns **403/401**, never **200** with foreign data.

---

## Sign-off

| Check | Pass | Date | Notes |
|-------|------|------|-------|
| 1 Password state | | | |
| 2 k6 | | | |
| 3 Cell concurrency | | | |
| 4 Provisioner what-ifs | | | |
| 5 Gateway outage | | | |
| 6 Isolation | | | |
