# AQREM — Product Functionality & Success Audit

**Audit date:** 2026-10-05  
**Scope:** End-to-end chain `Function → DB → Service → API → Frontend → User → Result`

Legend: **✓** working in UI+API | **~** partial | **✗** missing | Priority **P0–P3**

---

## Executive summary

The **core pilot workflow is implemented** (sign-in → project → source → index → questionnaire → generate → review → library → stale → export → audit). Gaps are mainly **lifecycle management** (edit/delete), **server-side upload preview**, **org admin**, and **operational visibility** (failed jobs history on source cards).

This pass implemented **P0/P1 fixes**: project scoping on APIs, evidence pagination + total, dashboard failed/indexing sources, RBAC on stale detail, mobile project selector, audit pagination, questionnaire CSV preview note, source job list API.

---

## Function audit table (condensed)

| Function | Purpose | User | Implementation | Gaps | Priority |
|----------|---------|------|----------------|------|----------|
| **Dashboard** | Workspace health & actions | All | ✓ overview metrics, questionnaires table, activity, review preview, library preview | No per-failed-job list on dashboard (link to Sources) | P2 |
| **Projects** | Scope isolation | Editor+ | ✓ create, list, summaries, detail hub | ✗ edit/delete/archive project | P1 |
| **Sources** | Connect & index evidence | Editor+ | ✓ create, GitHub connect, upload, sync, job poll | ✗ disconnect/delete; ~ last sync UI (API `GET /sources/{id}/jobs` added) | P1 |
| **Evidence** | Inspect indexed knowledge | All | ✓ search, filter, detail, pagination | List returns full content (heavy at scale) | P2 |
| **Questionnaires** | Import customer forms | Editor+ | ✓ create, upload, list (project filter) | ✗ server preview before replace; destructive upload | P1 |
| **Q workspace** | Complete questionnaire | Editor/Reviewer | ✓ filters, generate all, export, per-question review | No server pagination on questions | P2 |
| **AI answers** | Evidence-backed drafts | Editor+ | ✓ RAG + LLM + insufficient handling | Sync batch generate (no job progress) | P2 |
| **Citations** | Traceability | Reviewer | ✓ links to evidence detail | — | — |
| **Review queue** | Central review | Reviewer | ✓ search, project scope | ~ pagination UI, reason filters | P2 |
| **Answer library** | Reuse approved answers | All | ✓ search, validation, reuse in answering | ✗ deprecate entry; substring search only | P2 |
| **Stale answers** | Evidence freshness | Reviewer/Editor | ✓ list, detail, revalidate/regenerate/approve/reject | Bulk actions | P3 |
| **Export** | Deliver completed Q | Editor+ | ✓ CSV/XLSX, approved-only option | — | — |
| **Audit log** | Accountability | Admin/All | ✓ paginated list, action filter | ✗ export | P3 |
| **Project selector** | Isolation | All | ✓ sidebar + mobile; server filters on key lists | Sources still include org-wide (`project_id` null) by design | P1 note |
| **Auth** | Access control | All | ✓ login/register, session validation | ✗ password reset, SSO, invites | P2 |
| **RBAC** | Role enforcement | All | ✓ backend authoritative; UI on edit/review/stale | ✗ ORG_ADMIN admin UI | P2 |

---

## Acceptance checklist (pilot)

| Criterion | Status |
|-----------|--------|
| Create project | ✓ |
| Connect sources | ✓ |
| Ingest evidence | ✓ (requires worker + Postgres + Redis) |
| Inspect evidence | ✓ |
| Import questionnaire | ~ (upload works; preview is client CSV note only) |
| Generate answers | ✓ |
| Evidence-backed + insufficient | ✓ |
| Human edit/approve/reject | ✓ |
| Answer library + validation | ✓ |
| Stale detection & workflow | ✓ |
| Export | ✓ |
| Audit trail | ✓ |
| RBAC | ✓ backend; ~ UI hides actions |
| Org isolation | ✓ tested |
| Project isolation | ~ (explicit project filter + scoped lists; org-shared sources optional) |
| Errors understandable | ~ improved; API 403 still possible if UI bypassed |

---

## Implementation plan (remaining)

### P0
- None blocking pilot after this pass (assuming infra running).

### P1 (next)
- Project update (PATCH name/description)
- Source disconnect / soft-delete policy
- Questionnaire upload **dry-run** API before replace
- Surface **last sync job** on Sources cards (`fetchSourceJobs`)
- Review queue pagination

### P2
- Question list pagination
- Evidence list snippet mode
- Org user/role admin (ORG_ADMIN)
- Async bulk generate job

### P3
- Audit export, library deprecate, review assignee

---

## Security notes (audit)

- **Tenant isolation:** JWT + `X-Organization-Id`; membership checked (`dependencies.py`).
- **RBAC:** `require_role` on mutating routes; frontend mirrors for UX only.
- **Prompt injection:** Evidence passed to LLM — review `answering/service.py` and system prompts for instruction hardening (ongoing).
- **Secrets:** Not logged in audit helper; PAT in source config is dev-only pattern.
- **CORS:** Restricted outside development.

---

## Realistic workflow test

Use `scripts/seed_mvp_demo.py` + `tests/fixtures/customer_security_assessment.csv` with Docker (postgres, redis, worker) and `./scripts/start-web-one-port.sh`. Run `pytest tests/backend -q` and `cd frontend && npm run test && npm run build`.

---

## Chain reference (happy path)

```text
Register/Login → auth/me
Create project → POST /projects
Create source → POST /sources → POST sync → Celery → evidence rows
Upload questionnaire → POST .../upload → questions
Generate → POST .../generate → answers + citations
Review → approve → library upsert
Evidence change → staleness events → stale queue
Export → GET .../export/xlsx
Activity → GET /audit
```
