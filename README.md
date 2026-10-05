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

**Development (hot reload, port 5173):**

```bash
cd frontend && npm install && npm run dev
```

Vite binds to **`0.0.0.0:5173`**, so you can open the UI from other devices on your tailnet (not only `localhost`).

**One port (UI + API)** — good for demos and Tailscale (default **4173**, so Docker can keep **8000**):

```bash
chmod +x scripts/start-web-one-port.sh
./scripts/start-web-one-port.sh
```

Optional: `AQREM_WEB_PORT=4173 ./scripts/start-web-one-port.sh` (4173 is already the default).

The script builds the frontend if needed, syncs repo-root `.env` into `backend/.env` (same `SECRET_KEY` as Docker), ensures `.venv`, then serves UI + API together. On Tailscale, open **`http://<tailscale-ip>:4173`** and **sign in on that URL** (browser storage is per host; tokens from `:5173` or `:8000` do not apply). If you see “Invalid token”, use **Sign out** or open `/login?expired=1` and log in again. API docs: `/docs` on the same port.

### Access via Tailscale

On the machine running AQREM:

1. Ensure Tailscale is connected: `tailscale status`
2. Note your Tailscale IPv4: `tailscale ip -4` (example: `100.64.0.12`)
3. Start the **API** on all interfaces (Docker Compose already publishes `8000`; for local uvicorn use `--host 0.0.0.0`)
4. Start the **frontend**: `cd frontend && npm run dev`

From any device on the same tailnet, open:

```text
http://<your-tailscale-ip>:5173
```

The dev server proxies `/api` to `127.0.0.1:8000` on the host, so you do **not** need to set `VITE_API_BASE` for remote browsers.

Optional: call the API directly (Swagger, curl) at `http://<your-tailscale-ip>:8000/docs`.

If the page loads but API calls fail, confirm the API is running and reachable on port `8000`, and that your OS firewall allows inbound `5173` / `8000` on the Tailscale interface (`tailscale0`).

## Phase status (this repo)

| Phase | Status |
|-------|--------|
| 1 — Architecture & scaffolding | Implemented |
| 2 — Evidence ingestion & indexing | Implemented |
| 3 — Questionnaires, LLM answers, review UI | Implemented (core flow) |
| 4 — Answer library reuse | Implemented |
| 5 — Evidence staleness workflow | Implemented |
| 6 — Questionnaire export (XLSX/CSV) | Implemented |
| 7 — Production hardening & MVP UX | Implemented (core) |
| Azure deployment | Terraform skeleton (if present) |

## Security notes

- Tenant isolation enforced in API dependencies and scoped queries.
- OAuth tokens and document bodies are not written to audit logs.
- Configure real secrets via environment variables / Key Vault in production.
- `LLM_PROVIDER=mock` uses deterministic embeddings for local development.
