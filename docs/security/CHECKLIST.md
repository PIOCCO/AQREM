# Security Control Checklist

| Control | Status | Risk if missing | Evidence |
|---------|--------|-----------------|----------|
| JWT auth on API | Implemented | Critical | `get_tenant_context` |
| Org membership check | Implemented | Critical | `OrganizationMembership` query |
| RBAC on write/admin | Implemented | High | `require_role` |
| Cross-tenant IDOR tests | Implemented | High | `test_security_authorization.py` |
| RAG org filter + post-filter | Implemented | Critical | `RetrievalService` |
| LLM citation allowlist | Implemented | High | `guardrails.validate_structured_answer` |
| Evidence sanitization | Implemented | Medium | `guardrails.sanitize_evidence_content` |
| Rate limiting (LLM/login) | Implemented | High | `slowapi` on routes |
| Security headers | Implemented | Medium | `SecurityHeadersMiddleware` |
| CORS restrict production | Config required | High | `CORS_ALLOWED_ORIGINS` |
| Non-root API container | Implemented | Medium | `Dockerfile.api` |
| Azure OpenAI MI | Supported | High | `AZURE_OPENAI_USE_MANAGED_IDENTITY` |
| Secret scanning CI | Not in repo | Medium | Add gitleaks job |
| WAF / private endpoints | Not in repo | Medium | Azure landing zone |
| MFA / OIDC | Not implemented | Medium | Roadmap |
| Per-tenant AI quota | Not implemented | Medium | IP limits only |

**Recommended action:** Set `APP_ENV=production`, strong `SECRET_KEY`, `CORS_ALLOWED_ORIGINS`, disable mock LLM, enable MI + Key Vault, deploy Redis for rate limits when scaling horizontally.
