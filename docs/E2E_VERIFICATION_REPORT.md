# AQREM end-to-end verification report

**Date:** 2026-10-12  
**Environment:** Cloud agent VM (no Docker, no PostgreSQL listener on `:5432`)  
**Branch:** `cursor/full-e2e-azure-81ca`

## A. Overall status

| Area | Status |
|------|--------|
| Application startup (full stack) | **Not tested** — Docker unavailable; Postgres/Redis not running |
| Auth → export workflow (live UI) | **Not tested** — requires Postgres + API + worker |
| Backend integration tests (Postgres) | **Not executed** — 26/43 tests ERROR (connection refused) |
| Backend unit tests (no DB) | **Verified working** — 17 passed |
| LLM/Azure unit tests (mocked) | **Verified working** — 9 passed |
| Frontend build & unit tests | **Verified working** |
| Real Azure OpenAI | **Not verified** — no credentials; smoke script not run |

**Summary:** **Working with limitations** — codebase and mocked tests are healthy; full E2E and Azure live paths require local Docker and optional Azure config.

---

## B. Workflow results

| Step | Test performed | Result | Evidence |
|------|----------------|--------|----------|
| 1 Startup | `curl` dev frontend `:5173` | **Partial** | HTTP 200 from Vite (prior run); API/worker not started (no DB) |
| 1 Health | Code review `/health/ready` | **Not run live** | Implemented in `backend/app/main.py` |
| 2 Auth / project | `pytest test_project_create` | **Not run** | Postgres required |
| 3 Upload | UI/API upload | **Not run** | Requires stack |
| 4 Ingestion | `test_ingestion_demo_repo` | **Not run** | Postgres required |
| 5 Questionnaire | `test_questionnaire_*` | **Not run** | Postgres required |
| 6 AI answers | `test_questionnaire_answering` (mock LLM) | **Not run** | Postgres required; uses MockLLMProvider in CI |
| 6 Azure live | `scripts/azure_openai_smoke.py` | **Not run** | No `LLM_PROVIDER=azure` credentials |
| 7 Review queue | `test_staleness_workflow` / review tests | **Not run** | Postgres required |
| 8 Answer library | `test_answer_library` | **Not run** | Postgres required |
| 9 Export | `test_questionnaire_export` | **Not run** | Postgres required |
| 10 Audit | `test_staleness_workflow::test_audit_events_recorded` | **Not run** | Postgres required |
| Security | `test_security_*`, `test_tenant_isolation` | **Not run** | Postgres required |
| Chat API | `test_chat_ask.py` (added) | **Not run** | Postgres required |

---

## C. Issues found

| Severity | Issue | Root cause | Fix | Regression test |
|----------|-------|------------|-----|-----------------|
| **Medium** | Sign out unreachable from chat sidebar | Sign out control was `sr-only` | Restored profile menu with Sign out | Manual QA |
| **Low** | Regenerate could use stale conversation state | `onRegenerate` used closed-over state | Reload via `getConversation()` before `streamReply` | — |
| **Low** | No single script for local E2E | Missing orchestration | Added `scripts/run-e2e-verification.sh` | — |
| **Info** | Chat ask API untested in CI | No test file | Added `tests/backend/test_chat_ask.py` | Yes (needs Postgres) |

No Critical/High defects reproduced in code review without a running database.

---

## D. Actual test results

```bash
# Executed in cloud agent VM
cd /workspace/backend && pip install -e '.[dev]'
python3 -m pytest tests/backend -q
# → 17 passed, 26 errors (psycopg connection refused @ localhost:5432)

python3 -m pytest tests/backend/test_llm_config.py \
  tests/backend/test_llm_azure_provider.py \
  tests/backend/test_security_guardrails.py -q
# → 9 passed

cd /workspace/frontend && npm run test && npm run build
# → 16 passed; build OK
```

- **Lint:** Not configured as repo-wide gate (ruff in backend dev deps only).
- **Browser automation:** Not performed (auth + API dependency).
- **Database integration:** Blocked (no Postgres).
- **Azure OpenAI live request:** **Not executed.**

---

## E. Remaining blockers

1. **Docker** — required for `docker compose up` (Postgres/pgvector, Redis, Azurite, API, worker).
2. **`TEST_DATABASE_URL`** — `postgresql+psycopg://aqrem:aqrem@localhost:5432/aqrem_test` after `CREATE DATABASE aqrem_test`.
3. **Azure** — `LLM_PROVIDER=azure`, endpoint, deployments, key or managed identity; run `RUN_AZURE_SMOKE=1 python3 scripts/azure_openai_smoke.py`.
4. **Worker** — ingestion/embeddings require Celery worker + Redis.

---

## F. Exact next steps (local)

```bash
cp .env.example .env
docker compose up -d postgres redis azurite
docker compose exec postgres psql -U aqrem -c "CREATE DATABASE aqrem_test;"
chmod +x scripts/run-e2e-verification.sh
./scripts/run-e2e-verification.sh

# Full stack
docker compose up --build api worker
cd frontend && npm run dev

# Optional Azure
export LLM_PROVIDER=azure
# set AZURE_OPENAI_* ...
RUN_AZURE_SMOKE=1 ./scripts/run-e2e-verification.sh
```

Manual UI checklist after sign-in: create project → add source → sync → upload PDF/DOCX → questionnaire import → generate → review → export → chat ask with citations.
