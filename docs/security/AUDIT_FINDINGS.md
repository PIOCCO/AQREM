# Security Audit Findings (Pre-Hardening)

Based on repository inspection: FastAPI backend, React frontend, PostgreSQL+pgvector, Celery worker, Docker Compose, Terraform (Azure OpenAI only), JWT + org header multi-tenancy.

## 1. Critical vulnerabilities

| ID | Finding | Status after hardening |
|----|---------|------------------------|
| C1 | Production CORS could be empty or misconfigured; dev used `*` with credentials | **Mitigated** — explicit `CORS_ALLOWED_ORIGINS`; dev-only `*` |
| C2 | No rate limits on LLM generate / login (cost & abuse) | **Mitigated** — SlowAPI limits on auth + LLM routes |
| C3 | LLM output citations not validated against retrieval set (hallucinated IDs) | **Mitigated** — `validate_structured_answer` |

## 2. High-risk issues

| ID | Finding | Status |
|----|---------|--------|
| H1 | Retrieved evidence treated as trusted text in prompts | **Mitigated** — sanitization + untrusted-data instructions |
| H2 | Prompt injection via indexed documents not explicitly handled | **Partially mitigated** — pattern filter + system rules; not foolproof |
| H3 | API containers run as root | **Mitigated** — non-root `aqrem` user in API Dockerfile |
| H4 | No security HTTP headers on API responses | **Mitigated** — `SecurityHeadersMiddleware` |
| H5 | Default `SECRET_KEY` in `.env.example` | **Documented** — must rotate for production (existing) |

## 3. Medium / low

| ID | Finding | Notes |
|----|---------|-------|
| M1 | No CI/CD secret/SAST/container scanning in repo | Add in pipeline (documented) |
| M2 | No Azure private endpoints / full landing zone in Terraform | OpenAI module only by design |
| M3 | In-memory rate limits (single instance) | Use Redis backend for horizontal scale |
| M4 | No MFA / OIDC | JWT email/password only today |
| M5 | Retrieval preview returns full evidence bodies | List/detail caps exist elsewhere; preview still verbose |
| L1 | `--reload` in dev Dockerfile CMD | Removed from production API image CMD |

## 4. Architecture weaknesses

- Tenant isolation relies on consistent `organization_id` filters — generally present; added defense-in-depth on retrieval results.
- RAG authorization is org + project scope, not per-user document ACLs (by product design).
- Mock LLM in dev does not exercise Azure MI path without configuration.

## 5. Missing production controls

- Centralized log aggregation / SIEM wiring
- WAF / Azure Front Door
- Automated dependency/CVE gates in CI
- Per-tenant AI usage quotas (only IP rate limits today)
- Formal backup/DR runbooks (Postgres/blob left to deployment)

## 6. Recommended improvements (backlog)

1. OIDC / Entra ID for human auth; short-lived JWTs + refresh strategy.
2. Redis-backed rate limiting and per-org LLM quotas.
3. Private endpoints for Azure OpenAI, Postgres, Storage when full Azure stack lands.
4. CI: `gitleaks`, `pip-audit`, Trivy image scan, `terraform validate` + Checkov.
5. Retrieval preview response DTO with truncated content only.
6. Optional malware scanning on uploads (Defender for Storage / ClamAV sidecar).
