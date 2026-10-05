# AQREM

**Questionnaire & Evidence Management Platform** — connect company sources, index evidence, and generate traceable, evidence-backed questionnaire responses.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full data model, API boundaries, RAG design, and phased roadmap.

## Repository layout

- `backend/` — FastAPI API (multi-tenant, audit, ingestion orchestration)
- `worker/` — Celery workers (repository/document ingestion, embeddings)
- `frontend/` — React + TypeScript + Tailwind (V1 scaffold)
- `infra/` — Docker images + Terraform skeleton
- `tests/` — Backend tests (tenant isolation, ingestion, retrieval)
- `tests/fixtures/demo_saas_repo/` — Synthetic SaaS repo for local MVP demos

## Local development

### Prerequisites

- Docker & Docker Compose
- Python 3.12+ (optional for running API outside Docker)
- Node 20+ (frontend)

### Quick start

```bash
cp .env.example .env
docker compose up -d postgres redis azurite
docker compose up --build api worker
```

API: http://localhost:8000/docs

Create a test database for pytest:

```bash
docker compose exec postgres psql -U aqrem -c "CREATE DATABASE aqrem_test;"
pip install -e backend[dev]
TEST_DATABASE_URL=postgresql+psycopg://aqrem:aqrem@localhost:5432/aqrem_test pytest tests/backend -q
```

### Register & ingest demo repo (API)

```bash
# Register org + admin user
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"alex@acme.example","password":"password","full_name":"Alex","organization_name":"Acme Corporation"}'

# Create project, source, and trigger demo-path sync (set TOKEN/ORG from register response)
curl -s -X POST http://localhost:8000/api/v1/projects \
  -H "Authorization: Bearer $TOKEN" -H "X-Organization-Id: $ORG" \
  -H 'Content-Type: application/json' \
  -d '{"name":"SaaS Platform","description":"Core SaaS product"}'

curl -s -X POST http://localhost:8000/api/v1/sources \
  -H "Authorization: Bearer $TOKEN" -H "X-Organization-Id: $ORG" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Demo Repo","source_type":"folder_archive","project_id":"'$PROJECT'","scope":"project","config":{"demo_path":"/app/tests/fixtures/demo_saas_repo"}}'

curl -s -X POST http://localhost:8000/api/v1/sources/$SOURCE/sync \
  -H "Authorization: Bearer $TOKEN" -H "X-Organization-Id: $ORG"

# Retrieval preview (Phase 2 vertical slice)
curl -s -X POST http://localhost:8000/api/v1/retrieval/preview \
  -H "Authorization: Bearer $TOKEN" -H "X-Organization-Id: $ORG" \
  -H 'Content-Type: application/json' \
  -d '{"query":"Do you encrypt customer data at rest?","project_id":"'$PROJECT'"}'
```

### Frontend

```bash
cd frontend && npm install && npm run dev
```

## Phase status (this repo)

| Phase | Status |
|-------|--------|
| 1 — Architecture & scaffolding | Implemented |
| 2 — Evidence ingestion & indexing | Implemented |
| 3 — Questionnaires, LLM answers, review UI | Implemented (core flow) |
| 4 — Answer library reuse | Planned |
| 5 — Freshness / staleness | Basic version model |
| 6 — Export | Planned |
| 7 — Azure deployment | Terraform skeleton |

## Security notes

- Tenant isolation enforced in API dependencies and scoped queries.
- OAuth tokens and document bodies are not written to audit logs.
- Configure real secrets via environment variables / Key Vault in production.
- `LLM_PROVIDER=mock` uses deterministic embeddings for local development.
