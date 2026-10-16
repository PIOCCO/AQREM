# Proposal: narrow SECURITY DEFINER lookup functions (not implemented)

Status: proposal only (decision after CHECK 1). Nothing in this document is built.

## Problem
After migration 3 the control-plane role (`aqrem_app`, member of `aqrem_rls_control`) can read and
write **every row** of the identity/control tables (`users`, `organizations`, `organization_memberships`,
`user_invitations`, `employee_join_*`, `password_reset_tokens`, ...). It needs that today because a few
flows run before any organization is known:

| Flow | Code | What it needs before an org is known |
|---|---|---|
| Sign-in by email | `api/v1/auth.py::login` | user id, password hash, active flag, platform role, active memberships (org id, role, auth_version) |
| Invitation preview / accept | `services/invitations/*`, `auth.py` accept-invitation | invitation row by token hash -> org id, email, role, expiry, status |
| Employee join link / verification | `services/invitations/employee_join.py` | join link by token -> org id; verification by code hash |
| Password reset | `auth.py` forgot/reset | user by email; token row by hash |
| Super-admin console | `api/v1/admin.py`, platform_* services | genuinely cross-org (list orgs, members) |

Everything else (all `/org-admin/*`, chat, retrieval, documents, audit) already knows the org and
could run with `app.current_org` set and **no** cross-org group.

## Proposal
1. Functions owned by a dedicated NOLOGIN owner role `aqrem_lookup_owner` (member of `aqrem_rls_control`),
   `SECURITY DEFINER`, `SET search_path = pg_catalog, public`, `STABLE`, `REVOKE ALL ... FROM PUBLIC`,
   `GRANT EXECUTE` only to the runtime role. Each returns the minimum columns:

   ```sql
   aqrem_login_lookup(p_email text)
     RETURNS TABLE (user_id uuid, password_hash text, is_active bool, platform_role text,
                    platform_auth_version int, must_change_password bool)
     -- exact lower(email) match, at most 1 row
   aqrem_login_memberships(p_user_id uuid)
     RETURNS TABLE (organization_id uuid, role text, auth_version int, org_active bool, license_status text)
     -- only active memberships of that user
   aqrem_invitation_by_token(p_token_hash text)
     RETURNS TABLE (invitation_id uuid, organization_id uuid, email text, role text, expires_at timestamptz, status text)
   aqrem_join_link_by_token(p_token_hash text)   RETURNS TABLE (link_id uuid, organization_id uuid, expires_at timestamptz, active bool)
   aqrem_password_reset_by_token(p_token_hash text) RETURNS TABLE (user_id uuid, expires_at timestamptz, used bool)
   ```
   Callers pass hashes, never raw tokens; no function accepts patterns/LIKE or returns lists.
2. After lookup the app sets `app.current_org` to the resolved org and continues with normal RLS.
   Writes (accept invitation -> create membership/user) use one more definer function each
   (`aqrem_accept_invitation(...)`) or run with the org set (membership insert passes the org policy;
   creating a `users` row needs a policy allowing INSERT of a user that is then linked in the same txn,
   or a definer function).
3. Split roles: `aqrem_app` (runtime, **not** in `aqrem_rls_control`) for all requests/workers;
   `aqrem_platform` (in `aqrem_rls_control`) used only by the super-admin router (separate engine,
   `PLATFORM_DATABASE_URL`) and the startup bootstrap.

## How cross-org access shrinks
| | Today | After |
|---|---|---|
| Runtime role reads all `users` rows | yes | no - one row per email lookup, minimal columns |
| Runtime role reads all memberships/invitations | yes | no - only via user id / token hash |
| Runtime role reads password hashes in bulk | yes (`SELECT * FROM users`) | no |
| SQL injection in any org route -> dump identity tables | possible | limited to current org |
| Super-admin cross-org | runtime role | separate `aqrem_platform` role/engine |

## Risks
* SECURITY DEFINER pitfalls: search_path hijack (mitigated by fixed `search_path`, schema-qualified
  names, no CREATE on public for runtime roles), owner too powerful (use a dedicated owner).
* Email enumeration via timing is unchanged (exists today; mitigate in app with constant-time paths).
* Many call sites: invitation/join flows touch users + memberships + audit in one transaction; missing a
  path fails closed (sign-in/invite errors) - needs thorough tests, staged rollout behind a flag.
* Migrations must keep function signatures backward compatible (forward-only policy).
* Pi/local and tests must create the extra roles (scripts/sql/least-privilege-roles.sql).

## Effort estimate
| Item | Hours |
|---|---|
| SQL functions + owner role + migration 4 + grants | 4-6 |
| Refactor login, invitation preview/accept, join links, password reset to use functions | 8-12 |
| Separate platform engine/role for super-admin router + bootstrap | 4-6 |
| Remove `aqrem_rls_control` from runtime role; fix fail-closed fallout | 4-8 |
| Tests (direct-as-role + API flows), least-privilege flow script update | 6-8 |
| Docs / runbooks | 2 |
| **Total** | **28-42 h** |
