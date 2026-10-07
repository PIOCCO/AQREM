# Security Architecture

## System diagram (trust boundaries)

```text
                    ┌─────────────────────────────────────┐
                    │           User browser              │
                    └─────────────────┬───────────────────┘
                                      │ HTTPS
                    ┌─────────────────▼───────────────────┐
                    │  Frontend (static / Vite build)      │
                    │  Trust: presentation only            │
                    └─────────────────┬───────────────────┘
                                      │ Bearer JWT + X-Organization-Id
┌─────────────────────────────────────▼─────────────────────────────────────┐
│                         Backend API (FastAPI)                              │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────────────┐ │
│  │ AuthN JWT   │→ │ AuthZ RBAC   │→ │ Rate limits │→ │ Security headers │ │
│  └─────────────┘  └──────────────┘  └─────────────┘  └──────────────────┘ │
│         │                  │                    │                          │
│         ▼                  ▼                    ▼                          │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ Application services (Answering, Retrieval, Ingestion, Library)    │  │
│  │  • Tenant-scoped DB queries (organization_id)                      │  │
│  │  • RAG: project/source filters + post-filter org match             │  │
│  │  • LLM guardrails (sanitize evidence, validate citations)            │  │
│  └───────────┬───────────────────────┬────────────────────┬────────────┘  │
└──────────────┼───────────────────────┼────────────────────┼───────────────┘
               │                       │                    │
     ┌─────────▼─────────┐   ┌─────────▼────────┐  ┌───────▼────────┐
     │ PostgreSQL+pgvector│   │ Blob / local     │  │ Azure OpenAI   │
     │ (tenant rows)      │   │ uploads          │  │ (MI or KV key) │
     └────────────────────┘   └──────────────────┘  └────────────────┘
               ▲
     ┌─────────┴─────────┐
     │ Celery worker       │
     │ (indexing, sync)    │
     └─────────────────────┘
```

## Authentication

- Email/password registration and login; bcrypt password hashes.
- JWT access tokens; `X-Organization-Id` selects org membership.
- Membership required per request (`get_tenant_context`).

## Authorization

- RBAC roles: `VIEWER`, `EDITOR`, `REVIEWER`, `ORG_ADMIN` (see `app/core/roles.py`).
- Mutations require `require_role(...)` on routes.
- Resources checked with `organization_id == tenant.organization_id` (404 on cross-tenant IDOR).

## AI / RAG data flow

```text
User question (authenticated, EDITOR+)
    ↓ clamp_question / max length
RetrievalService.retrieve(organization_id, project_id?, source_id?)
    ↓ SQL filters on organization_id (+ project scope)
    ↓ vector + keyword search
    ↓ post-filter organization_id match
Evidence blocks → sanitize_evidence_content → wrap_evidence_for_prompt
    ↓
Azure OpenAI / Mock (system prompt + JSON user payload)
    ↓ max_tokens, structured JSON
validate_structured_answer (citation allowlist)
    ↓
Answer persisted + audit metadata (no raw prompts in audit by default)
```

**Authorization model for RAG:** retrieval never runs without `organization_id` from JWT membership. Project scope limits chunks to project-linked evidence (plus org-scoped rows where model allows). There is no end-user-level document ACL below org/project.

## Secrets

- Env / Key Vault for `SECRET_KEY`, DB URL, Azure OpenAI key.
- Prefer `AZURE_OPENAI_USE_MANAGED_IDENTITY=true` in Azure (see `infra/terraform/`).
- Terraform does not output keys.

## Logging / audit

- `audit_events` table: who, action, resource, metadata (generation stats, not full LLM I/O).
- API production errors generic (no stack traces to client).

## Network (current)

- Docker Compose exposes Postgres/Redis/API on localhost for dev.
- Azure Terraform module: configurable `public_network_access_enabled` on OpenAI account.
