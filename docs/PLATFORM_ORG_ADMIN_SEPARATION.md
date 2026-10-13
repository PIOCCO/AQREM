# Platform Super Admin (L1) vs Customer Org Admin (L2)

## Route namespaces

| Surface | URL namespace | API prefix | JWT audience |
|--------|---------------|------------|--------------|
| **Super Admin (L1)** | `/super-admin` (legacy `/master-admin`, `/platform-admin` redirect) | `/api/v1/admin/*`, `/api/v1/master/*` | `aqrem-master` |
| **Customer org admin (L2)** | `/admin/*` | `/api/v1/org-admin/*`, `/api/v1/org-admin/access/*` | `aqrem-org-admin` |
| **Employee workspace (L3)** | `/`, `/chat`, `/evidence`, … | `/api/v1/projects`, `/api/v1/evidence`, … | `aqrem-employee` or `aqrem-org-admin` |

Public: `/login`, `/accept-invite`, `/join`.

## Permission matrix (summary)

| Capability | SUPER_ADMIN | PLATFORM_SUPPORT | PLATFORM_BILLING | ORG_ADMIN | EDITOR/VIEWER |
|------------|-------------|------------------|------------------|-----------|---------------|
| Manage organizations | yes | read metadata | read + license | no | no |
| Platform audit / deployments | yes | read | no | no | no |
| Org user / ACL admin | no* | no | no | yes | no |
| Questionnaires / evidence | no* | no | no | per role | per role |

\*Platform staff use **platform JWT only**; tenant data plane rejects `aqrem-master` tokens. No default access to customer content.

Full platform matrix: `backend/app/core/permissions.yaml` and `GET /api/v1/admin/permissions/matrix`.

## Enforcement

- **Server:** `get_platform_user` for L1; `get_tenant_context` for L2/L3 (tenant audiences only).
- **Org binding:** Tenant JWT `organization_id` must match `X-Organization-Id` when both are present.
- **UI:** `RequireSuperAdmin` (platform JWT), `RequireTenantWorkspace` (tenant JWT), `RequireOrgAdminOnly` (org admin permission).

## First super admin

Set `PLATFORM_ADMIN_EMAIL` and `PLATFORM_ADMIN_PASSWORD` in `.env`. On API startup, `ensure_platform_admin` creates the bootstrap user. Sign in at `/login` → redirected to `/super-admin`.

Do not assign `platform_role` to customer users unless they are intentional platform staff.
