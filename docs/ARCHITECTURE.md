# AQREM — Questionnaire & Evidence Management Platform

## 1. Current project structure

```
/workspace
├── README.md
├── docker-compose.yml          # Local: Postgres+pgvector, Redis, Azurite, API, worker
├── .env.example
├── backend/                    # FastAPI application
│   ├── pyproject.toml
│   ├── alembic/
│   └── app/
│       ├── main.py
│       ├── core/               # config, security, tenancy, dependencies
│       ├── db/                 # session, base
│       ├── models/             # SQLAlchemy ORM
│       ├── schemas/            # Pydantic API models
│       ├── api/v1/             # REST routers
│       ├── services/
│       │   ├── auth/           # provider abstraction (dev JWT, Entra-ready)
│       │   ├── storage/        # Azure Blob abstraction (+ local dev)
│       │   ├── llm/            # Azure OpenAI abstraction
│       │   ├── ingestion/      # parsers, chunkers, indexers
│       │   ├── github/         # OAuth + repo sync
│       │   └── retrieval/      # RAG (Phase 3)
│       └── audit/
├── worker/                     # Celery app + task modules
│   └── app/
│       ├── celery_app.py
│       └── tasks/
├── frontend/                   # React + TypeScript + Tailwind (scaffold)
├── infra/
│   ├── terraform/              # Azure Container Apps (skeleton)
│   └── docker/
├── docs/
│   └── ARCHITECTURE.md
└── tests/
    ├── backend/
    └── fixtures/
```

## 2. Recommended architecture

```text
┌─────────────┐     HTTPS      ┌──────────────┐
│   React UI  │ ─────────────► │   FastAPI    │
└─────────────┘                │   (API)      │
                               └──────┬───────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
              ┌──────────┐    ┌────────────┐    ┌─────────────┐
              │ Postgres │    │   Redis    │    │ Azure Blob  │
              │ pgvector │    │  (Celery)  │    │  (files)    │
              └──────────┘    └─────┬──────┘    └─────────────┘
                                    │
                                    ▼
                              ┌──────────┐
                              │  Worker  │
                              │ (Celery) │
                              └──────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              GitHub API      Parsers/embed    Azure OpenAI
```

**Principles**

- **Evidence-first**: all answers cite `evidence_items`; LLM is downstream of retrieval.
- **Scope-aware retrieval**: every query filters by `organization_id` and optional `project_id` / `source_id`.
- **Async ingestion**: uploads and GitHub sync enqueue Celery tasks; API returns job status.
- **Replaceable integrations**: auth, blob, and LLM behind interfaces; V1 includes dev/local implementations.

## 3. Database schema

### Core tenancy

| Table | Purpose |
|-------|---------|
| `organizations` | Tenant root |
| `users` | Global user identity |
| `organization_memberships` | `user_id`, `organization_id`, `role` (ORG_ADMIN, EDITOR, REVIEWER, VIEWER) |
| `projects` | Scoped workspace under org |
| `audit_events` | Immutable action log |

### Sources & evidence

| Table | Purpose |
|-------|---------|
| `sources` | Connector instance (upload, github, folder); `scope` = org \| project \| source |
| `source_sync_jobs` | Ingestion run status, stats, errors |
| `github_connections` | Installation/token metadata per org (encrypted at rest in production) |
| `github_repo_configs` | repo, branch, project association |
| `evidence_items` | Chunk/symbol with content, provenance, embedding |
| `evidence_item_versions` | Historical content for freshness (GitHub commit tracking) |
| `ingestion_ignore_rules` | Configurable glob patterns per org/project |

### Questionnaires & answers (Phase 3+)

| Table | Purpose |
|-------|---------|
| `questionnaires` | Metadata, project link |
| `questions` | Extracted question rows |
| `answers` | Draft/approved text, confidence, status |
| `answer_evidence_links` | M:N answer ↔ evidence |
| `answer_library_entries` | Normalized reusable answers |
| `answer_staleness_flags` | Evidence change → dependent answers |

### Key `evidence_items` columns

```text
id, organization_id, project_id (nullable), source_id
source_type, scope
file_name, file_path, content, content_type, language
repository, branch, commit_hash
line_start, line_end, symbol_name, symbol_kind
chunk_index, metadata (JSONB)
embedding vector(1536)
content_hash, last_verified_at
created_at, updated_at
```

Indexes: `(organization_id, project_id)`, `(source_id)`, HNSW/IVFFlat on `embedding`, GIN on `content` (tsvector) for hybrid search.

## 4. API design

Base path: `/api/v1`. All routes require auth except `/health` and OAuth callbacks.

| Area | Methods | Notes |
|------|---------|-------|
| Auth | `POST /auth/login` (dev), `GET /auth/me` | Entra: `/auth/entra/callback` later |
| Organizations | CRUD | ORG_ADMIN |
| Projects | CRUD | EDITOR+ |
| Sources | CRUD, `POST .../sync` | EDITOR+ |
| Uploads | `POST /sources/{id}/files` multipart | Size/type validation |
| GitHub | `GET /github/install`, `POST /github/repos`, webhook | Least privilege |
| Evidence | `GET /evidence`, `GET /evidence/{id}` | Scoped list/search |
| Ingestion jobs | `GET /jobs/{id}` | Status polling |
| Questionnaires | CRUD, upload, extract | Phase 3 |
| Questions/Answers | generate, review actions | Phase 3 |
| Answer library | search, reuse | Phase 4 |
| Export | `POST /questionnaires/{id}/export` | Phase 7 |
| Dashboard | `GET /dashboard/metrics` | Aggregates |
| Audit | `GET /audit` | ORG_ADMIN, REVIEWER |
| Settings | ignore rules, org settings | ORG_ADMIN |

**Authorization**: middleware resolves JWT → user → membership for `X-Organization-Id` header. SQLAlchemy queries always include `organization_id` filter via session context.

## 5. Frontend page structure

React Router layout matching product screens:

```text
/login
/app (authenticated shell + sidebar)
  /dashboard
  /projects
  /projects/:projectId
  /sources
  /sources/new
  /sources/:sourceId
  /evidence
  /questionnaires
  /questionnaires/:id
  /questionnaires/:id/questions/:questionId/review  ← primary workflow
  /answer-library
  /answer-library/:id
  /audit
  /settings
```

V1 scaffold: shell + Dashboard/Sources/Evidence placeholders wired to API. Review workspace prioritized in Phase 3.

Design reference: light theme, KPI cards, evidence citation panel (see product mockup).

## 6. Evidence ingestion pipeline

```text
Source created (upload | github | archive)
        ↓
Enqueue source_sync_job (Celery)
        ↓
Fetch raw bytes (Blob / GitHub API / upload buffer)
        ↓
Apply ignore rules (node_modules, dist, .git, binaries, …)
        ↓
Parse by type
   ├── Documents: PDF, DOCX, XLSX, CSV, MD, TXT, JSON, YAML
   └── Code: extension + optional Tree-sitter symbols (functions/classes)
        ↓
Chunk (size overlap; code preserves line ranges)
        ↓
Extract metadata (path, language, repo, commit, lines, symbol)
        ↓
Compute content_hash; diff vs previous → version rows + staleness hooks
        ↓
Embed batches (LLM provider embeddings API)
        ↓
Upsert evidence_items (+ tsvector for keyword leg)
        ↓
Mark job complete; audit log
```

**GitHub flow**

```text
Connect GitHub App / OAuth
  → store installation scoped to organization
  → user selects repo + branch + project
  → worker clones shallow or uses GitHub Contents API + tarball
  → index incrementally (commit_hash cursor)
```

## 7. RAG / retrieval architecture (Phase 3)

```text
Question (+ optional project scope)
   ↓
Query understanding (keywords + embedding)
   ↓
Parallel retrieval (all filtered by org_id + scope):
   • pgvector cosine similarity
   • PostgreSQL full-text (ts_rank)
   • Code path boost when question mentions config/infra/code terms
   ↓
Reciprocal rank fusion / weighted merge
   ↓
Top-K evidence (cap token budget for LLM)
   ↓
LLM structured answer + evidence_ids
```

Tests must assert Project A evidence never appears for Project B queries.

## 8. LLM abstraction

```python
class LLMProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    async def generate_answer(self, request: AnswerRequest) -> StructuredAnswer: ...
```

Implementations:

- `AzureOpenAIProvider` (production)
- `MockLLMProvider` / optional local for CI

System prompt enforces evidence-only answers, `evidence_sufficiency`, citations, no chain-of-thought.

## 9. Multi-tenancy model

- **Row-level isolation**: every tenant table has `organization_id NOT NULL` (except global `users`).
- **Request context**: `TenantContext(organization_id, user_id, role)` set in FastAPI dependency.
- **Repository pattern**: `scoped_query(Model)` applies org filter; project-scoped resources also validate `project.organization_id`.
- **Storage**: blob paths `{org_id}/{project_id}/{source_id}/...`.
- **Workers**: jobs carry `organization_id`; tasks reject missing scope.

No cross-tenant joins without explicit super-admin mode (not in V1).

## 10. Implementation phases

| Phase | Scope | Status |
|-------|--------|--------|
| 1 | Repo layout, Docker, config, auth abstraction, models skeleton | **This PR** |
| 2 | Ingestion: upload, GitHub architecture, chunk, embed, index | **This PR** |
| 3 | Questionnaires, retrieval, LLM answers, review UI | Next |
| 4 | Answer library + similarity reuse | Next |
| 5 | Freshness / staleness detection | Next |
| 6 | Export XLSX/CSV | Next |
| 7 | Terraform/Azure deployment hardening | Parallel |

**Vertical slice target (end of Phase 2)**:

```text
GitHub / Folder → ingestion → indexed evidence → (stub) retrieve by question text
```

Phase 3 completes LLM + citations UI.

## 11. Main technical risks

| Risk | Mitigation |
|------|------------|
| Large repo ingestion time/memory | Shallow clone, batch embed, incremental commits, file size caps |
| Embedding cost | Batch API, dedupe by content_hash, skip unchanged chunks |
| Cross-tenant data leak | DB session scoping + integration tests on every retrieval path |
| LLM hallucination | Strict prompt + insufficient-evidence path + require evidence_ids |
| GitHub token security | GitHub App, encrypted secrets, minimal repo scope |
| PDF/DOCX parsing quality | Pluggable parsers; store raw in blob for re-index |
| pgvector scale | IVFFlat/HNSW tuning; partition by organization_id if needed |
| Stale evidence false positives | Version by content_hash; line-level diff for GitHub |

## 12. MVP acceptance criteria

Maps to product scenario §24:

1. Create Organization — API + UI
2. Create Project "SaaS Platform"
3. Connect GitHub repository — OAuth/App + repo picker
4. Index repository — async job completes
5. Upload company documents — PDF/DOCX/etc.
6. Upload questionnaire (20 questions) — Phase 3
7. Generate answers — Phase 3
8. Exact supporting evidence — Phase 3
9. Confidence / evidence strength — Phase 3
10. Insufficient evidence when unsupported — Phase 3
11. Approve answers — Phase 3
12. Reuse similar approved answer — Phase 4
13. Change source file — re-sync
14. Detect potentially stale — Phase 5 (basic model in Phase 2)
15. Export questionnaire — Phase 6

**Phase 2 exit criteria**

- File and archive upload ingested into `evidence_items` with embeddings
- GitHub repo config stored; sync task indexes demo repo with line citations
- Evidence API returns scoped results
- Ignore rules configurable
- Audit events for source indexed
- Tests: tenant isolation on evidence queries; retrieval returns relevant chunks for sample question (keyword/vector)
