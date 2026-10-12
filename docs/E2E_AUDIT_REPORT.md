# AQREM end-to-end audit report

**Date:** 2026-10-12  
**Scope:** Full-stack workflow, Azure OpenAI, security, tests

## Baseline (this environment)

| Check | Result |
|-------|--------|
| Frontend `npm run build` | Pass (on agent run) |
| Frontend `npm run test` | 16/16 pass |
| Backend unit tests (no Postgres) | 9/9 pass (`test_llm_*`, guardrails) |
| Backend full suite | **Blocked** — Docker/Postgres not available in cloud agent VM |
| Live Azure OpenAI | **Not verified** — no credentials; use `scripts/azure_openai_smoke.py` locally |

## Implemented workflow (code review + existing tests when DB available)

| Step | Status | Notes |
|------|--------|-------|
| Auth + org tenancy | ✓ | JWT + `X-Organization-Id`; tests in `test_tenant_isolation.py`, `test_security_*` |
| Projects + sources | ✓ | Create project with initial source; sync via Celery worker |
| Ingestion PDF/DOCX/code | ✓ | `parsers.py`, indexer + embeddings via LLM provider |
| pgvector retrieval | ✓ | `RetrievalService` with org/project filters |
| Questionnaire CSV/XLSX import | ✓ | Server-side extract; tests in `test_questionnaire_*` |
| Azure OpenAI answers | ✓ | `AzureOpenAIProvider` (OpenAI SDK); mock for CI |
| Citations + guardrails | ✓ | `validate_structured_answer`, injection sanitization |
| Review + library + stale | ✓ | Dedicated tests |
| Export CSV/XLSX | ✓ | Backend-generated blobs |
| Chat UI + API | ✓ | `POST /api/v1/chat/ask` wired to same RAG/LLM stack |

## Changes in this pass

1. **Azure OpenAI:** Official `openai` SDK, bounded retries, strict `LLM_PROVIDER=azure` (no silent fallback to mock).
2. **Config:** Env aliases including `AZURE_OPENAI_DEPLOYMENT`; production validation for Azure settings.
3. **Health:** `/health/live`, `/health/ready` (database + LLM config).
4. **Chat API:** Evidence-grounded ask endpoint for the ChatGPT-style UI.
5. **Tests:** `test_llm_config.py`, `test_llm_azure_provider.py` (mocked SDK).
6. **Docs:** `docs/AZURE_OPENAI.md`, smoke script `scripts/azure_openai_smoke.py`.

## Known gaps (unchanged / P1 backlog)

- Project **edit/archive** APIs not implemented (documented in product audit).
- Source **delete/disconnect** lifecycle incomplete.
- Questionnaire upload **dry-run** before replace not implemented.
- No server-side **conversation persistence** (chat history is browser localStorage).
- Async **bulk generate** job with progress UI not implemented.

## Security

- Tenant isolation: server-side on all scoped routes (verify with full pytest when Postgres available).
- Secrets: not logged; Azure keys backend-only.
- Document prompt-injection mitigations in `guardrails.py`.

## Commands to run locally

```bash
cp .env.example .env
docker compose up -d postgres redis azurite
docker compose up --build api worker
cd frontend && npm install && npm run dev

# Full backend tests
docker compose exec postgres psql -U aqrem -c "CREATE DATABASE aqrem_test;"
pip install -e backend[dev]
TEST_DATABASE_URL=postgresql+psycopg://aqrem:aqrem@localhost:5432/aqrem_test python3 -m pytest tests/backend -q

# Optional Azure verification
export LLM_PROVIDER=azure
# ... set AZURE_OPENAI_* ...
python3 scripts/azure_openai_smoke.py
```
