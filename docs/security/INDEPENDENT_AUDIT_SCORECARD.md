# Independent Security Review Scorecard

**Reviewer stance:** External auditor; prior hardening not assumed correct.  
**Branch reviewed:** `cursor/aqrem-evidence-platform-00e3` (third independent pass).  
**Date:** 2026-10-07

## Methodology

- Full static review: backend, frontend, worker, Docker, Terraform, CI config
- Attacker analysis: IDOR/BOLA, cross-tenant, JWT abuse, RAG poisoning, uploads, SSRF, secrets
- Automated: `pytest` security suite; repo pattern scan (`sk-`, `AKIA`, private keys); `ruff`; `terraform validate` when CLI present
- **Not executed in cloud agent VM:** Docker-based integration tests (no Docker), live Azure pentest, DAST

## Scorecard

| Area | Status | Risk | Evidence |
|------|--------|------|----------|
| Authentication | Partial | Medium | JWT + bcrypt; register gated by `ALLOW_PUBLIC_REGISTRATION`; 24h TTL; no MFA/OIDC |
| Authorization | Good | Low–Med | RBAC + org checks on API routes |
| Tenant isolation | Good | Low | SQL org filters + post-filter; `test_security_tenant_matrix.py` |
| AI security | Partial | Medium–High | System rules, clamping, citation allowlist; injection not fully preventable |
| RAG security | Partial | Medium | Org/project scoped retrieval; untrusted evidence wrapping; no doc-level ACL |
| API security | Partial | Medium | SlowAPI limits, security headers; in-memory rate limits |
| Database | Partial | Medium | Parameterized vector SQL + ORM; dev compose uses default creds |
| File security | Improved | Medium | Extension/size limits; basename uploads; zip-slip filter; no AV |
| Secrets | Partial | High (ops) | Config tokens stripped at create; response redaction; prod `SECRET_KEY` guard |
| Docker | Partial | Low–Med | API + worker non-root (`Dockerfile.api`, `Dockerfile.worker`) |
| Terraform | Partial | Low–Med | OpenAI module; scoped RBAC; public network default on account |
| Azure | Not in repo | High (ops) | No full landing zone / private endpoints in this repo |
| CI/CD | Improved | Medium | `.github/workflows/security.yml` (pytest, ruff, terraform, pip-audit) |
| Monitoring | Missing | High | No SIEM/alert wiring in application repo |
| Backup/DR | Missing | High | Not defined in application repo |

## Findings by severity

### CRITICAL (operational — deployment blockers)

| ID | Finding | Location | Required fix |
|----|---------|----------|--------------|
| C-OPS-1 | Weak/default secrets if deploy ignores guards | Env / Key Vault | Unique `SECRET_KEY` (32+ chars), DB creds, rotate OpenAI keys |
| C-OPS-2 | No TLS in application repo | Ingress / Container Apps | HTTPS-only at edge |

### HIGH

| ID | Finding | Status |
|----|---------|--------|
| H-1 | GitHub PAT in API responses | **Fixed** — serializer redaction |
| H-2 | Inline GitHub token in production | **Fixed** — connect endpoint blocked outside `development` |
| H-3 | Secrets via `SourceCreate.config` | **Fixed** — `sanitize_source_config_for_storage` |
| H-4 | OpenAPI in production | **Fixed** — disabled when `APP_ENV=production` |
| H-5 | Unbounded LLM/register abuse | **Fixed** — rate limits on login/register/generate/preview/stale |
| H-6 | Upload path / zip-slip | **Fixed** — `safe_blob_filename`, `resolve_under_root`, archive path filter |
| H-7 | Open registration in production | **Mitigated** — `ALLOW_PUBLIC_REGISTRATION=false` recommended; enforced when set |
| H-8 | Production boot with weak JWT secret | **Fixed** — Settings validator fails fast |
| H-9 | No runtime monitoring/SIEM | **Open** — operational |
| H-10 | No backup/DR | **Open** — operational |

### MEDIUM

| ID | Finding | Notes |
|----|---------|-------|
| M-1 | Regex-only injection sanitizer | Process + human review still required |
| M-2 | Answer prose not scanned for exfil | Citations constrained |
| M-3 | In-memory SlowAPI | Use Redis backend when horizontally scaled |
| M-4 | JWT 24h lifetime | Shorten + refresh for production |
| M-5 | `demo_path` worker indexing | Dev-only guard added |
| M-6 | Terraform OpenAI public access default | Set `public_network_access_enabled=false` + PE for prod |

### LOW / INFORMATIONAL

- CSRF: low risk for Bearer-token SPA
- Frontend not a security boundary (correct)
- Azurite dev key in compose is public Azurite sample (dev only)

## AI attack assessment

| Attack | Prevented? | Notes |
|--------|------------|-------|
| Direct prompt injection (question) | Partially | Length clamp + system prompt |
| Indirect injection (evidence) | Partially | Markers + `[filtered]`; not foolproof |
| Cross-tenant RAG | Yes (tested paths) | Org in SQL + post-filter + matrix test |
| Citation to other tenants' IDs | Yes | `validate_structured_answer` allowlist |
| Tool/function abuse | N/A | No tool calling |
| System prompt exfil | Partially | Policy text only |
| Unauthenticated cost abuse | Yes | 401 on protected routes |
| Authenticated cost abuse | Partially | Rate limits; no per-org quota |

## Tenant isolation tests

- `test_security_tenant_matrix.py` — User A / Tenant A vs Tenant B: project, source sync, evidence, questionnaire, stale answer, retrieval preview
- `test_security_authorization.py` — cross-org project access
- `test_security_source_config_api.py` — token not persisted via create API

## Tooling run (this pass)

| Tool | Result |
|------|--------|
| `pytest tests/backend/test_security_*.py` | Pass (unit); DB-backed tests need Postgres |
| Repo secret pattern scan | No `sk-` / `AKIA` / private keys |
| `ruff check` | Run in CI workflow |
| `terraform validate` | CI job; skipped locally if CLI missing |
| `pip-audit` | CI job (non-blocking `|| true`) |

See also [FINAL_REPORT.md](./FINAL_REPORT.md) and [AUDIT_FINDINGS.md](./AUDIT_FINDINGS.md).
