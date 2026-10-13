# Three-layer link matrix (verified 2026-03-13)

Tenant key: `organizations.id` (`organization_id` in JWT and headers). Environment record: `client_environments` (`environment_id`, `employee_url`, `admin_url`).

**Status legend:** Working | Partly | Missing | Insecure

## Before → after (this audit)

| # | From → To | Purpose | Mechanism | AuthZ | Before | After | Evidence |
|---|-----------|---------|-----------|-------|--------|-------|----------|
| 1 | L1 → tenant | Create org + license | `POST /api/v1/admin/organizations` | `require_platform_admin` + master `aud` | Working | Working | `test_s1_provision_and_telemetry_pipeline` |
| 2 | L1 → env | Provision URLs | `POST /api/v1/master/organizations/{id}/provision` | platform admin | Partly (UI missing) | Partly | `test_s1_*`, `master.py` |
| 3 | L1 → L2/L3 URLs | Entry points | `ClientEnvironment.employee_url`, `admin_url` | N/A (stored metadata) | Partly | Partly | local adapter sets `/chat`, `/admin` |
| 4 | L1 → L2/L3 | License/seats | `organizations.license_*` + `org_allows_sign_in` | DB + login gate | Working | Working | `test_s3_*`, `test_s2_*` |
| 5 | L1/L2 → user | Invitations | `provision_user_invitation` | seat check | Working | Working | `test_admin_provisioning.py` |
| 6 | IdP → L1 | Platform login | JWT `aud=aqrem-master` | `is_platform_admin` | Partly | Working | `test_s8_*`, `dependencies.require_platform_admin` |
| 7 | IdP → L2 | Org admin | JWT `aud=aqrem-org-admin` | `_require_org_admin_surface` | Working | Working | `test_client_admin_dashboard.py` |
| 8 | IdP → L3 | Employee | JWT `aud=aqrem-employee` | `get_tenant_context` + role | Working | Working | `test_e2e_authorization.py` |
| 9 | Token cross-use | Layer isolation | aud + org claims | default deny | Partly | Working | `test_s8_token_confusion_matrix` |
| 10 | L2 → vault | Model token | `ClientSecretStore` | org admin | Partly (Azure stub) | Partly | `test_model_token_not_in_db_or_audit` |
| 11 | L3 → LLM | Inference | `get_llm_provider()` global | N/A | Missing | Missing | not wired to per-tenant vault |
| 12 | L2 → storage → index | Documents | org-admin upload + worker | tenant_id on rows | Working | Working | ingestion tests |
| 13 | L3 → index | RAG | `RetrievalService` / chat | `organization_id` filter | Working | Working | `test_tenant_isolation.py` |
| 14 | L2 → L1 telemetry | Ops metadata | `ingest_org_telemetry` → `control_plane_events` | allow-list schema | Missing | Working | `test_l2_telemetry_persisted_for_l1` |
| 15 | L1 telemetry ingest | Direct ingest | `POST /master/telemetry` | platform admin | Working | Working | `test_telemetry_allowlist.py` |
| 16 | All → audit | Activity | `record_audit` | tenant scoped | Working | Working | audit API tests |
| 17 | L1 license → L2 copy | Platform action text | audit metadata `source=platform_control_plane` | audit read | Missing | Partly | `presentation.py` template |
| 18 | L2 → revoke L3 session | Deactivate member | `auth_version` on membership | JWT check | Missing | Working | `test_s4_deactivate_revokes_session` |
| 19 | Support break-glass | Emergency access | — | — | Missing | Missing | `docs/CONTROL_PLANE.md` |
| 20 | Offboard delete | Data removal | suspend only | — | Partly | Partly | no hard-delete org API |
| 21 | S2S / mTLS | Service calls | — | — | Missing | Missing | single-app JWT model |
| 22 | Webhooks signed | GitHub etc. | — | — | Missing | Missing | no webhook routes |

## Propagation time (license)

License and seat limits are read from PostgreSQL on each request (`get_tenant_context`, `assert_can_add_seat` with `db.refresh(org)`). **Target &lt; 60s** is met in-process immediately after commit; no redeploy required.

## Logging

Audit: `audit_events` (tenant-scoped). Control plane: `control_plane_events`. Application logs: request middleware (no token body logging in org-admin token tests).
