# Post-separation security verification report

**Branch:** `cursor/super-admin-separation-81ca`  
**Baseline commit reviewed:** `7c3c481` (extended by worker hardening + tests in this pass)  
**Date:** 2026-10-13  

This report reflects **independent code inspection and executed tests**, not prior agent summaries alone.

---

## 1. Background processing

### Inventory

| Mechanism | Location | Purpose |
|-----------|----------|---------|
| **Celery** | `worker/app/celery_app.py`, `worker/app/tasks/ingestion.py` | `run_source_sync` — GitHub archive fetch or blob download → `index_files` |
| **Enqueue** | `backend/app/api/v1/sources.py`, `org_admin.py` | Called only after authenticated tenant context creates `SourceSyncJob` |
| **FastAPI `BackgroundTasks`** | — | **None found** |
| **APScheduler / cron** | — | **None found** |
| **Export generation** | `questionnaires.py`, `audit.py` | Synchronous HTTP handlers under `get_tenant_context` |
| **AI / retrieval** | `retrieval.py`, `chat.py`, `stale_answers.py` | Request-scoped; org from tenant context |

### Findings

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| BG-1 | **High** | `run_source_sync(job_id, organization_id)` did not verify `job.organization_id` / `source.organization_id` against the payload. On **managed colocated** DB (shared PostgreSQL), a forged Celery message could process another tenant's job if the broker were compromised. | **Fixed** — validation + blob prefix checks; errors truncated in job metadata |
| BG-2 | **Medium** | Blob paths in `job.stats` were downloaded without verifying `{organization_id}/` prefix. | **Fixed** — `_validate_blob_paths_for_org` before job enters `RUNNING` |
| BG-3 | **Low** | Task failure stored `str(exc)[:2000]` which could theoretically include sensitive paths; now capped to first line / 500 chars in DB. | **Mitigated** |
| BG-4 | **Informational** | Celery broker trust boundary assumed; no mTLS/task signing documented. | **Open** — compensating control: network isolation + Redis auth in production |
| BG-5 | **Informational** | Retries use same `(job_id, organization_id)` args; no automatic retry wrapper found in code. | **Verified** |

**Regression tests:** `tests/backend/test_worker_ingestion_isolation.py`

---

## 2. Evidence and storage isolation

### Lifecycle traced

1. **Upload (employee):** `POST /api/v1/sources/{id}/files` — org-scoped source, blob path `{org_id}/{source_id}/{safe_name}` (`safe_blob_filename`).
2. **Upload (org admin docs):** `POST /api/v1/org-admin/documents/upload` — same path pattern + malware scan.
3. **Persistence:** Content indexed into `evidence_items` via worker; metadata includes `organization_id`.
4. **Storage:** `LocalBlobStorage` / Azure — `resolve_under_root` blocks `..` escape.
5. **Read API:** `GET /api/v1/evidence/*` — filters `organization_id == tenant.organization_id` + ACL.
6. **Retrieval / AI:** `RetrievalService` SQL includes `organization_id = :org_id` + ACL fragment.
7. **Delete:** No dedicated public delete endpoint on `evidence.py` (items removed via source/org lifecycle).
8. **Export:** Questionnaire CSV/XLSX under tenant context + org-scoped `build_export_rows`.

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| EV-1 | **Informational** | No signed URLs; API returns content bytes/json (no presigned object URLs). | **Verified** |
| EV-2 | **Low** | Path traversal on upload filename blocked by `safe_blob_filename` (unit tested). | **Verified** |
| EV-3 | **Informational** | Cross-tenant evidence access returns **404** (tested). | **Verified** |
| EV-4 | **Informational** | Retrieval preview excludes other org content (tested with persisted rows). | **Verified** |

**Tests:** `tests/backend/test_evidence_storage_lifecycle.py`, `test_security_tenant_matrix.py`, `test_layer_separation_extended.py`

---

## 3. Browser E2E

Playwright config: `frontend/playwright.config.ts` (preview on `:5173`, employee auth via `e2e/auth.setup.ts` + `.qa-credentials.json`).

Platform specs require `QA_PLATFORM_PASSWORD` (not stored in `.qa-credentials.json`).

**Executed in this pass** (API on `:8000`, preview on `:5173`):

| Suite | Result |
|-------|--------|
| `e2e/super-admin-route-guards.spec.ts` (public-dark) | **3 passed** |
| `e2e/platform-admin-privacy.spec.ts` (public-dark, `QA_PLATFORM_PASSWORD` set) | **1 passed** |
| `e2e/auth.setup.ts` + `e2e/admin-console-nav.spec.ts` (sidebar-layout) | **5 passed** |

**Not fully executed:** Full 20-spec matrix (dark-theme platform login, org-invitations, product walkthrough, etc.).

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| E2E-1 | **Informational** | Many specs `test.skip` when passwords unset — avoids false green but reduces CI signal unless secrets configured. | **Open** |
| E2E-2 | **Low** | Super-admin / admin anonymous + employee redirect coverage added in `super-admin-route-guards.spec.ts`. | **Verified** (3 tests) |

---

## 4. Database isolation (RLS)

See `docs/TENANT_ISOLATION_ASSESSMENT.md`.

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| DB-1 | **Informational** | RLS **not** enabled; isolation is ORM/query filters + tenant session routing. | **Documented** |
| DB-2 | **Informational** | Implementing RLS on shared pool requires per-request `SET LOCAL`, platform bypass role, and worker changes. | **Deferred** — not implemented in this pass |
| DB-3 | **Low** | Direct SQL with application DB role could read all tenants on colocated DB if credentials leak. | **Compensating:** secret rotation, network policy, no ad-hoc SQL |

---

## 5. Production configuration

| Control | Implementation | Notes |
|---------|----------------|-------|
| Platform bootstrap | `bootstrap.py`, `config.py` | Prod disables password resync; tests in `test_bootstrap_platform_admin.py` |
| JWT | HS256, iss/aud/exp enforced | Default TTL 24h (`access_token_expire_minutes`) |
| Passwords | bcrypt | `hash_password` / `verify_password` |
| CORS | `CORSMiddleware`, explicit origins list | Credentials allowed; `X-Organization-Id` header allowed |
| CSRF | N/A for Bearer API | SPA uses Authorization header, not cookie sessions for API |
| Rate limits | slowapi on login, org-admin mutations, retrieval, LLM | `rate_limit_enabled` default true |
| Security headers | `SecurityHeadersMiddleware` | nosniff, DENY frame, referrer-policy |
| OpenAPI | Disabled in production | `main.py` |
| Dependency audit | `pip audit` | **Unavailable** in current venv (`unknown command`) |
| Audit logging | `record_audit` on admin/ingestion actions | Not exhaustive for every read |

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| CFG-1 | **Medium** | 24h JWT TTL is long for high-security deployments. | **Open** — product/config choice |
| CFG-2 | **Informational** | No HttpOnly session cookie for API; theft via XSS is a frontend concern. | **Documented** |
| CFG-3 | **Informational** | Support / break-glass customer data access feature **not implemented**. | **Verified** |

---

## 6. Commands and results

```bash
# Backend security suites (includes new worker + evidence tests)
pytest tests/backend/test_interface_separation.py \
  tests/backend/test_layer_separation_extended.py \
  tests/backend/test_bootstrap_platform_admin.py \
  tests/backend/test_jwt_security.py \
  tests/backend/test_security_tenant_matrix.py \
  tests/backend/test_security_authorization.py \
  tests/backend/test_worker_ingestion_isolation.py \
  tests/backend/test_evidence_storage_lifecycle.py -q
# Result: see CI output below

cd frontend && npm run build
# Result: success

cd frontend && npm run test -- --run src/lib/authRouting.test.ts
# Result: 2 passed

# Playwright (platform privacy + employee setup), secrets via env:
cd frontend && QA_PLATFORM_PASSWORD=*** npx playwright test e2e/platform-admin-privacy.spec.ts --project=public-dark
cd frontend && npx playwright test --project=setup --project=sidebar-layout
# Results: recorded at execution time
```

---

## 7. Limitations (honest)

- **Not** complete penetration testing or regulatory compliance attestation.
- **Not** all Playwright specs run with full QA credential set in this environment.
- **Not** Redis/Celery broker hardening verified.
- **Not** customer-dedicated PostgreSQL mode exhaustively tested (only colocated test DB).
- **Fixed** one confirmed high-severity worker validation gap (BG-1/BG-2).

---

## 8. Support access

Emergency platform access to customer **content** is **not** implemented. Platform JWT cannot call tenant data-plane endpoints (`get_tenant_context` rejects `aqrem-master`).
