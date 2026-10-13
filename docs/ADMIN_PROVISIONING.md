# Administrator-provisioned access

Public self-registration is **disabled**. Clients receive access only after a **platform administrator** creates their organization and invitation.

## Bootstrap platform administrator

Set in `.env` (repo root):

```env
PLATFORM_ADMIN_EMAIL=admin@yourcompany.example
PLATFORM_ADMIN_PASSWORD=your-strong-password
```

On API startup, if no user exists with that email, AQREM creates a platform administrator account (password is hashed; never logged).

Sign in at `/login` → redirected to **`/platform-admin`**.

## Provision a client

1. **Create organization** — default test setup uses `license_limit=0` and `license_status=test`.
2. **Provision user** — enter email, name, role; copy the **one-time** `/accept-invite?token=…` link.
3. Client opens the link, sets a password, and is signed in to their organization.

## License semantics

| Field | Meaning |
|-------|---------|
| `license_limit` | Maximum **active** memberships (licensed seats). **`0` = zero seats** — no sign-in for `active` orgs. |
| `license_status` | `active`, `suspended`, or `test` (separate from seat count). |

**Test mode** (`LICENSING_TEST_MODE=true`, non-production only): organizations with `license_status=test` may sign in and operate even when `license_limit=0`. In **production**, test mode is forced off and `test` status does not grant access.

## API

Platform routes (Bearer token, platform admin user): `/api/v1/admin/*`

Public registration: **not available** (`POST /api/v1/auth/register` is not routed — **404**).
