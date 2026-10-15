# Pilot runbook (local production-like stack)

No Azure subscription required. Requires **Docker** and **docker compose** on your machine.

## 1. Start the stack

```bash
./scripts/start-local-prod-stack.sh
```

**Expected:** Services `postgres`, `redis`, `azurite`, `fake-azure-openai`, `model-gateway`, `api`, `worker`, `web` become healthy; script prints URLs for web (:5173), API (:8000), gateway (:8088).

**If it fails:** `docker compose -f docker-compose.local-prod.yml logs api worker model-gateway` — common causes: port 5432/8000 already in use, insufficient RAM for web `npm ci`.

## 2. Smoke test

```bash
./scripts/smoke-local-prod-stack.sh
```

**Expected:** `PASS` lines from gateway contract, model integration script, and `tests/e2e/test_local_stack_core.py`; ends with `SMOKED PASS`.

## 3. Manual golden path (browser)

1. Open http://127.0.0.1:5173 — login with seeded user (create via platform admin bootstrap if first run).
2. Org admin → Data storage → validate and activate PostgreSQL.
3. Upload a `.txt` policy with a unique sentence (e.g. `PILOT-FACT-001: backup retention is 365 days.`).
4. Wait until document status leaves **indexing** (worker logs).
5. Chat: ask about the fact → streamed answer with citation.
6. Ask something not in the document → insufficient-evidence style answer.

## 4. Failure injection (fake Azure)

```bash
docker compose -f docker-compose.local-prod.yml exec fake-azure-openai \
  sh -c 'export FAKE_AZURE_MODE=429'  # restart container with env in compose override
```

Retry chat — expect user-safe rate-limit message, not a hang.

## 5. Stop

```bash
docker compose -f docker-compose.local-prod.yml down
```

## 6. Only humans with Azure

See `docs/azure/CONFIG_CONTRACT.md` and `infra/verification/DEV_VERIFICATION_CHECKLIST.md` for real subscription onboarding (`terraform apply`, Key Vault keys, Brevo DNS).
