# Administrator-provisioned access

Public self-registration is **disabled**. Clients receive access only after a **platform administrator** creates their organization and invitation.

## Bootstrap platform administrator

Set in `.env` (repo root):

```env
PLATFORM_ADMIN_EMAIL=admin@yourcompany.example
PLATFORM_ADMIN_PASSWORD=your-strong-password
```

On API startup, if no user exists with that email, AQREM creates a platform administrator account (password is hashed; never logged).

Sign in at `/login` → redirected to **`/super-admin`**.

## Public app URL (invitation links)

Set the browser-facing base URL (protocol, host, and port — no trailing slash):

```env
PUBLIC_BASE_URL=http://100.80.43.124:5173
```

(`PUBLIC_APP_URL` / `APP_PUBLIC_BASE_URL` are aliases.)

Production (Azure Container Apps or custom domain): set the same variable in container app **Configuration → Environment variables** (or Key Vault reference), e.g. `https://your-app.azurecontainerapps.io`. Ensure the ingress forwards `Host`, `X-Forwarded-Host`, and `X-Forwarded-Proto` so invitation APIs can fall back when the env var is missing.

If `PUBLIC_BASE_URL` is unset, the API logs a warning and derives the base URL from those headers on each request (never returns a bare `/invite/...` path in JSON responses).

Optional frontend fallback: `VITE_PUBLIC_APP_URL` (same value) when displaying URLs before an API round-trip.

Invitation URLs are built server-side:

- Organization admin: `{PUBLIC_APP_URL}/invite/admin/{token}`
- Employee join link: `{PUBLIC_APP_URL}/join/{token}`

## Provision a client

1. **Create organization** — default test setup uses `license_limit=0` and `license_status=test`.
2. **Provision user** — enter email, name, role; copy the full **`invitation_setup_url`** from the API/UI.
3. Client opens the link, sets a password, and is signed in to their organization admin console (`/admin`) when invited as org admin.

## License semantics

| Field | Meaning |
|-------|---------|
| `license_limit` | Maximum **active** memberships (licensed seats). **`0` = zero seats** — no sign-in for `active` orgs. |
| `license_status` | `active`, `suspended`, or `test` (separate from seat count). |

**Test mode** (`LICENSING_TEST_MODE=true`, non-production only): organizations with `license_status=test` may sign in and operate even when `license_limit=0`. In **production**, test mode is forced off and `test` status does not grant access.

## API

Platform routes (Bearer token, platform admin user): `/api/v1/admin/*`

Public registration: **not available** (`POST /api/v1/auth/register` is not routed — **404**).
