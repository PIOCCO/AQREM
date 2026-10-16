# Tenant isolation audit (shared tier) — Oct 2026

Scope: every `db.get(...)`/query on tenant models in `backend/app/api` and `backend/app/services`,
raw SQL (`text(...)`) in retrieval/library/embedding health, blob path generation/deletion,
chat shares, org-admin and platform-admin routes.

## Model
* Every tenant row carries `organization_id`. The request org comes from `get_tenant_context`
  (JWT `sub` + `X-Organization-Id`, membership verified in the control DB).
* Retrieval SQL always has `organization_id = :org_id`; results are re-filtered by org in Python.
* Blobs: `<organization_id>/<source_id>/<file>` and `<organization_id>/questionnaires/<id>/<file>`
  (helpers `org_blob_path` / `assert_blob_in_org` in `services/storage/path_utils.py`).
* Chats are not stored server-side (browser-local); only explicit share snapshots
  (`chat_conversation_shares`) are stored, scoped by organization_id + token.

## Gaps found and fixed
| # | Gap | Impact | Fix |
|---|-----|--------|-----|
| 1 | `chat/service._project_label` loaded any `project_id` from the request without an org check | Org A could learn the **name** of an org B project by passing its UUID to `/chat/ask` (confirmed by test before fix) | Label returned only if project.organization_id == caller org |
| 2 | Blob deletes (document delete, org purge) did not verify the path is inside the org prefix | Defense in depth: a corrupted/forged `blob_path` row could delete another org's object | `assert_blob_in_org` before every delete; ingestion uses the same helper |
| 3 | Blob paths built with ad-hoc f-strings | Risk of inconsistent prefixes | Centralised `org_blob_path` |
| 4 | Retrieval ignored project/source/ACL narrowing even when `PRODUCT_V1=false` | Intra-org (not cross-org) over-sharing in legacy mode | Narrowing restored when `PRODUCT_V1=false`; with `PRODUCT_V1=true` (default) retrieval is intentionally org-wide |

## Checked, no gap
Sources, jobs, evidence get/list, projects, questionnaires, answer library (ORM and vector SQL),
org-admin documents/members/audit/retry/delete, platform admin membership routes (`membership.organization_id == organization_id`),
chat share get/revoke (token + org), ingestion task (job/source/org consistency + blob prefix).

## Known, not changed (product decisions)
* `PRODUCT_V1=true` deliberately disables document-level ACL inside one organization
  (`evidence_acl_filter` no-op). Existing tests `test_document_acl_leak_matrix`, `test_inner_org_document_access`
  and `test_tenant_isolation::test_project_scope_isolation` encode the old intra-org behaviour and fail
  on the base branch as well. They are **intra-org**, not cross-org.
* No PostgreSQL row-level security; isolation is enforced in the application layer. Dedicated tier gives
  physical isolation (own DB).

Proof: `tests/backend/test_cross_org_isolation.py` (two orgs, retrieval service, retrieval preview,
chat ask + stream, header spoofing, evidence list/get, org-admin documents list/delete/retry, members, audit,
chat shares, blob prefix guard).
