# Tenant isolation and database security assessment

## Current isolation mechanism (verified in code)

1. **Authentication:** JWTs are issued with audience claims (`aqrem-master`, `aqrem-org-admin`, `aqrem-employee`). `decode_access_token` enforces issuer, signature, expiry, and audience on each request.
2. **Plane separation:** Platform routes use `get_platform_user` and reject tenant audiences. Tenant data-plane routes use `get_tenant_context`, which **rejects** `aqrem-master` tokens outright.
3. **Organization binding:** For tenant tokens, `organization_id` in the JWT must match `X-Organization-Id` when both are present (`Organization context mismatch` → 403).
4. **Membership:** Active `OrganizationMembership` required; role comes from membership, not client-supplied body fields on ordinary APIs.
5. **Query scoping:** Services and repositories filter by `tenant.organization_id` / resource ownership; cross-tenant IDs typically yield **404** (no existence leak) on evidence, projects, and questionnaires.
6. **Org availability:** Inactive organizations and license/sign-in guards return **403** before business logic.

**Row-Level Security (PostgreSQL RLS):** Not enabled. All isolation is application-layer via SQLAlchemy sessions and explicit `organization_id` filters. Connection pooling uses a shared DB role; tenant context is not propagated via `SET app.current_org` today.

## RLS suitability

| Factor | Assessment |
|--------|------------|
| Single shared DB user for app | RLS would require `SET LOCAL` per transaction or per-request; must align with connection pool checkout/checkin. |
| Platform admin queries | L1 operations span all tenants; would need a **BYPASSRLS** role or separate connection for platform APIs only. |
| Migrations / jobs | Celery workers would need the same tenant context injection or a privileged role with narrow job scope. |
| Benefit vs complexity | High for defense-in-depth if direct SQL access is a threat; moderate effort to avoid breaking platform console and background tasks. |

**Recommendation:** Keep application-layer isolation as the primary boundary (already tested). Consider RLS as a phased hardening step only after: (1) dedicated pool settings for platform vs tenant, (2) audit of all raw SQL, (3) integration tests that connect as the app DB user and attempt cross-tenant `SELECT`.

## Emergency support access

No product feature grants platform staff implicit read access to customer questionnaires, evidence, or answer libraries. Platform JWTs are blocked from tenant data-plane endpoints by design.

If break-glass support is required later, it should be:

- **Off by default**
- **Explicitly authorized** (ticket + customer approval)
- **Time-limited** with automatic expiry
- **Fully audited** (who, which org, which resources, duration)
- **Narrowly scoped** (metadata vs content separation where possible)

Current `PLATFORM_SUPPORT` permissions in `permissions.yaml` allow organization metadata and deployment reads, not tenant content APIs.

## Secret management (platform bootstrap)

- Configure `PLATFORM_ADMIN_EMAIL` and `PLATFORM_ADMIN_PASSWORD` via environment or secret store — never commit values.
- In **production**, `platform_admin_sync_password` is forced **false** so restarts do not overwrite an existing super-admin password from env.
- Bootstrap logs only the email address when creating a new account, not the password.

See `docs/PLATFORM_ORG_ADMIN_SEPARATION.md` for route/API matrix and test references.
