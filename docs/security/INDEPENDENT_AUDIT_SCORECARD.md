# Independent Security Review Scorecard

**Reviewer stance:** External auditor; prior hardening not assumed correct.  
**Branch reviewed:** `cursor/aqrem-evidence-platform-00e3` (post-hardening + this pass).  
**Date:** 2026-10-07

## Methodology

- Static review of backend, frontend, Docker, Terraform, security modules
- Attacker-oriented analysis (IDOR, cross-tenant, AI abuse, secret exposure)
- Automated: `pytest` guardrail/redaction/tenant tests; repo pattern scan for keys; `terraform validate` when available
- **Not executed here:** live penetration test, DAST, production Azure config review (no credentials)

## Scorecard

| Area | Status | Risk | Evidence |
|------|--------|------|----------|
| Authentication | Partial | Medium | JWT + bcrypt; 24h token; no MFA/OIDC |
| Authorization | Good | Low–Med | RBAC + org checks on routes |
| Tenant isolation | Good | Low | Org filters; matrix test added |
| AI security | Partial | Medium–High | Guardrails + citation allowlist; injection not fully preventable |
| RAG security | Partial | Medium | Org/project SQL filters + post-filter; no per-user ACL |
| API security | Partial | Medium | Rate limits, headers; in-memory limits |
| Database | Partial | Medium | ORM + parameterized vector SQL; default creds in compose |
| File security | Partial | Medium | Extension/size checks; no AV scan |
| Secrets | Partial | High (ops) | No keys in git scan; PAT blocked in prod; default SECRET_KEY |
| Docker | Partial | Medium | API non-root; worker still root |
| Terraform | Partial | Low–Med | OpenAI module only; public access default true |
| Azure | Not deployed | High (ops) | No full landing zone in repo |
| CI/CD | Missing | High | No automated security pipeline in repo |
| Monitoring | Missing | High | No SIEM/alert wiring in repo |
| Backup/DR | Missing | High | Not defined in application repo |

## Findings by severity

### CRITICAL (operational — not code-only)

| ID | Finding | Location | Fix |
|----|---------|----------|-----|
| C-OPS-1 | Default `SECRET_KEY` / DB passwords in `.env.example` | Deploy config | Rotate all secrets before prod |
| C-OPS-2 | No TLS termination defined in app repo | Edge/ingress | HTTPS only at gateway |

### HIGH (addressed in this review where code applies)

| ID | Finding | Status |
|----|---------|--------|
| H-1 | GitHub PAT returned in `SourceResponse.config` | **Fixed** — redaction serializer |
| H-2 | Inline GitHub token stored in prod | **Fixed** — rejected outside `development` |
| H-3 | OpenAPI `/docs` exposed when `APP_ENV=production` | **Fixed** — disabled |
| H-4 | Register / stale regenerate LLM without rate limits | **Fixed** |
| H-5 | Retrieval preview returned full evidence bodies | **Fixed** — summary + sanitize |
| H-6 | No CI secret/SAST/container gates | **Open** — operational |

### MEDIUM

| ID | Finding | Notes |
|----|---------|-------|
| M-1 | Prompt injection filter is regex-only | Expected; review workflow required |
| M-2 | Model answer text not scanned for exfil patterns | Citations constrained; prose not |
| M-3 | Worker container runs as root | Harden Dockerfile.worker |
| M-4 | Rate limits per-IP in-memory | Use Redis when scaling |
| M-5 | JWT 24h lifetime | Shorten + refresh for prod |
| M-6 | `list_sources` includes org-scoped sources when filtering by project | By design; document |

### LOW / INFORMATIONAL

- CSRF low risk for Bearer-token SPA API
- Mock LLM does not test Azure MI path
- Frontend is not a security boundary (correct)

## AI attack assessment

| Attack | Prevented? | Notes |
|--------|------------|-------|
| Direct prompt injection in question | Partially | Clamped length; system rules |
| Indirect injection in evidence | Partially | `[filtered]` + untrusted markers; bypassable |
| Cross-tenant via RAG | Yes (in tested paths) | Org ID in SQL + post-filter + matrix test |
| Citation to non-retrieved IDs | Yes | `validate_structured_answer` |
| Tool/function abuse | N/A | No tool calling |
| System prompt exfil via model | Partially | Prompt rules only; not cryptographic |
| Cost abuse unauthenticated | Yes | 401 on protected routes |
| Cost abuse authenticated | Partially | Rate limits; no per-org quota |

## Tests added this review

- `test_security_tenant_matrix.py` — cross-tenant project/source/evidence/questionnaire/stale/retrieval
- `test_security_source_redaction.py` — config secret redaction

## Tooling run

| Tool | Result |
|------|--------|
| `pytest tests/backend/test_security_*.py` | Pass (no DB tests if Postgres down) |
| Repo `sk-` / `AKIA` pattern scan | No matches |
| `pip-audit` | Not available in environment |
| `terraform validate` | Pass when Terraform installed |

See also [FINAL_REPORT.md](./FINAL_REPORT.md) and [AUDIT_FINDINGS.md](./AUDIT_FINDINGS.md).
