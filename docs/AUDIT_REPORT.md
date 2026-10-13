# AQREM independent QA / security / UX audit

**Auditor:** Cloud agent (independent of prior UI passes)  
**Date:** 2026-10-12  
**Branch:** `cursor/qa-release-audit-81ca` (from `cursor/chat-ui-intent-81ca`)  
**Environment:** Linux VM, Postgres local, API `uvicorn` on :8000, Vite preview :5173, **no Docker/worker** in this VM.

## STEP 0 — Baseline (verified)

| Check | Result | Evidence |
|--------|--------|----------|
| `frontend`: `npm ci`, `npm run build` | **Pass** | 1 warning: JS bundle >500 kB |
| `frontend`: `npm run test` (Vitest) | **42/42 pass** | After `vitest.config.ts` excludes `e2e/` |
| `frontend`: `npm run test:e2e` (Playwright) | **21/21 pass** | Public + authenticated axe + contrast regression |
| `backend`: `pytest tests/backend` | **100/100 pass** | `TEST_DATABASE_URL=...aqrem_test`, 550 deprecation warnings (pathspec) |
| API `/health` | **Pass** | `{"status":"ok"}` after local uvicorn start |
| Docker Compose stack | **Not run** | `docker: command not found` on VM |
| Browsers Chrome/Edge/Firefox/Safari matrix | **Not run** | Only Playwright Chromium |
| Full core journey (index → export questionnaire) | **Not run end-to-end in UI** | No worker/Celery; would need scripted API + UI session |
| RAG 30-question eval | **Not re-run manually** | Covered by existing `test_rag_product_quality.py` in backend suite |
| Load / chaos / backup / restore | **Not run** | Out of scope for this environment |

### Defects found (summary)

| ID | Screen / area | Steps | Expected | Actual | Severity | Status |
|----|---------------|-------|----------|--------|----------|--------|
| D-001 | Test suite | `npm run test` | Unit tests only | Vitest executed Playwright specs → false failures | Major | **Fixed** — `vitest.config.ts` |
| D-002 | Workspace (dark) | Open Dashboard/Projects with dark theme | Cards/buttons use dark surfaces | `@apply bg-surface` rendered **white** cards with dark text tokens (contrast ~2.5:1) | **Blocker** | **Fixed** — explicit `background-color: var(--color-surface)` on `.aq-card`, `.ref-metric-card`, `.aq-btn-secondary` |
| D-003 | All workspace pages | axe on main content | WCAG AA | Hard-coded `text-slate-*` on dark background | Major | **Fixed** — semantic `text-fg*` tokens bulk migration |
| D-004 | Evidence | Open `/evidence` | Filter controls labeled | `<select>` without accessible name | Major | **Fixed** — `aria-label` on filter + search |
| D-005 | Chat | axe | No critical issues | Hidden file input without label; scope link contrast 4.48:1 | Major | **Fixed** — file input `aria-label`; scope links use `--color-link` |
| D-006 | Sidebar | User footer | No nested interactive | `<Link>` inside `<button>` | Major | **Fixed** — split button / link |
| D-007 | E2E auth | Playwright setup | Dark default during audit | Settings test left theme **light** in shared storage | Major | **Fixed** — setup forces `aqrem_theme=dark`; settings test restores dark |
| D-008 | npm deps | `npm audit` | No critical | 2 critical, 6 high (vitest/vite chain) | Major | **Open** — needs dependency upgrade plan |
| D-009 | Production ops | Docker/worker/backup | Documented run | Not validated in this VM | Major | **Open** |
| D-010 | Core product journey | UI walk employee/admin | Full questionnaire export | Not executed in browser this run | Major | **Open** — API tests only |
| D-011 | Platform admin UI | `/master-admin` | Full console test | Not browser-tested (bootstrap user created via API) | Minor | **Open** |
| D-012 | SECRET_KEY | `.env` | Strong secret in dev | `change-me-in-production` | Major (prod) | **Needs decision** — OK for local dev only |

### Screenshots (employee, dark mode, post-fix)

Captured under `/opt/cursor/artifacts/screenshots/` during Playwright audit:  
`chat-dark.png`, `dashboard-dark.png`, `projects-dark.png`, `sources-dark.png`, `evidence-dark.png`, `questionnaires-dark.png`, `review-queue-dark.png`, `answer-library-dark.png`, `activity-dark.png`, `settings-dark.png`, `settings-light.png`.

## Section notes (1–8)

### 1 Functional
Backend integration tests cover tenant isolation, invitations, review queue, answer library, questionnaires, chat intent, and RAG quality. **UI-level end-to-end journey not re-run** (worker/indexing/export in browser).

### 2 UI/UX
Dark default confirmed (`data-theme=dark`). **Blocker D-002** fixed. Responsive/layout: Playwright 1280px, no horizontal scroll assertion on routes. Copy: no `MVP`/`TODO` in `frontend/src` (grep).

### 3 Accessibility
Playwright + axe on `main` (color-contrast via dedicated computed-style regression). **21 E2E tests pass.** Manual keyboard-only and SR testing **not performed**.

### 4 Security
- `pytest` includes IDOR/tenant tests — **100 pass**.
- Public registration **403** (test_admin_provisioning).
- Security headers on `/health`: `X-Frame-Options: DENY` (CSP/HSTS not fully audited).
- `npm audit` / `pip audit` — **not clean** (frontend criticals).
- Pen-test style XSS/SQLi/prompt-injection **not re-run beyond existing backend tests**.

### 5 RAG
Relies on **`tests/backend/test_rag_product_quality.py`** and related tests — **not independently re-scored** this run.

### 6 Performance
Bundle warning only; no load test.

### 7 Observability / ops
Not validated (no Docker logs, backup drill).

### 8 Documentation
README exists; runbook depth **not audited** line-by-line.

## Regression tests added

- `frontend/vitest.config.ts` — exclude Playwright specs from Vitest.
- `frontend/e2e/authenticated-audit.spec.ts` — route smoke + axe (main).
- `frontend/e2e/contrast-regression.spec.ts` — computed contrast on dashboard cards/buttons.
- `frontend/e2e/auth.setup.ts` + `scripts/qa-provision-tenant.sh` — reproducible employee session.
- Evidence filter `aria-label` (D-004).

## Files changed (this audit)

See git diff on branch; highlights: `frontend/src/index.css`, workspace pages (token migration), `EvidencePage.tsx`, `ChatSidebar.tsx`, `ChatComposer.tsx`, E2E/vitest configs, `docs/AUDIT_REPORT.md`, `docs/RELEASE_READINESS.md`.
