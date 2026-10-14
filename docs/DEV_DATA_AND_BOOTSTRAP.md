# Development data, bootstrap, and clean slate

## What runs automatically (runtime)

| Component | When | Creates tenant data? |
|-----------|------|----------------------|
| `main.py` lifespan | API startup | **No organizations.** Applies schema patches (`CREATE TABLE` / `ADD COLUMN` only). |
| `ensure_platform_admin()` | API startup | **Only** if `PLATFORM_ADMIN_EMAIL` and `PLATFORM_ADMIN_PASSWORD` are set — one platform user row if missing. Never creates organizations. |
| `ensure_default_access_groups()` | When an org is created via API | Access group **definitions** for that org (not sample tenants). |
| `LLM_PROVIDER=mock` | Chat/RAG calls | Mock **model responses**, not DB rows for orgs/members. |
| Frontend `localStorage` | Browser | Auth token, theme, chat UI state — not platform org list. |

There is **no** MSW/mock API layer in the production frontend bundle. E2E tests may stub routes under `frontend/e2e/` only.

## Bootstrap super admin (required for empty DB)

Set in `backend/.env` or repo-root `.env` (never commit real passwords):

```env
PLATFORM_ADMIN_EMAIL=you@company.example
PLATFORM_ADMIN_PASSWORD=use-a-strong-secret
PLATFORM_ADMIN_SYNC_PASSWORD=false
```

- First startup creates the super admin if the email does not exist.
- With `PLATFORM_ADMIN_SYNC_PASSWORD=false` (default), existing passwords are **not** reset on restart.
- Add a **second** super admin from Super Admin → Team & roles (banner warns when count &lt; 2).

Optional dev-only flag (off by default):

```env
LICENSING_TEST_MODE=true
```

Allows `license_status=test` orgs to sign in; forced off when `APP_ENV=production`.

## Manual dev seed (optional)

```bash
cd backend && python ../scripts/seed_mvp_demo.py --email YOUR_ADMIN --password '...'
```

Refuses to run when `APP_ENV=production`. Does not run on API startup.

## Wipe tenant data (development DB only)

**Backup first:**

```bash
pg_dump "postgresql://aqrem:aqrem@localhost:5432/aqrem" -Fc -f aqrem-dev-backup.dump
```

**Dry run (counts only):**

```bash
cd backend && python ../scripts/wipe_dev_tenant_data.py --dry-run
```

**Apply:**

```bash
cd backend && python ../scripts/wipe_dev_tenant_data.py --apply
```

Keeps `is_platform_admin` users; removes all organizations, memberships, invitations, employee links, tenant users, and org-scoped audit rows. Refuses `APP_ENV=production` and non-local DB hosts unless `--allow-production-url`.

**Restore backup:**

```bash
pg_restore -d "postgresql://aqrem:aqrem@localhost:5432/aqrem" --clean --if-exists aqrem-dev-backup.dump
```

## Audit: removed / not tenant “mock” data

- **Removed:** Members directory **404 → /members** fallback in `platformAdminApi.ts` (could mask stale APIs).
- **Removed:** Default `LICENSING_TEST_MODE=true` and `PLATFORM_ADMIN_SYNC_PASSWORD=true` (no silent env-driven churn).
- **Kept:** Test fixtures under `tests/`; `scripts/seed_mvp_demo.py` (manual); `MockLLMProvider` for local LLM; `demo_path` ingestion (development-only guard in worker).
