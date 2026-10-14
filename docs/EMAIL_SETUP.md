# Email setup (Brevo transactional)

## Step A — Audit (before this integration)

| Area | Location | Previous behavior |
|------|----------|-------------------|
| Email stubs | `backend/app/services/email/delivery.py`, `invitations.py` | `EMAIL_DELIVERY_MODE=log` logged only; no real sends |
| Invitation URLs | `backend/app/services/invitations/invite_urls.py` | `PUBLIC_APP_URL` / `APP_PUBLIC_BASE_URL` via `build_invite_url()` |
| Org admin invite | `provision_admin_invitation()`, `admin_invitations.py` | Link in API/UI; optional stub “email sent” |
| Resend invite | `resend_admin_invitation()`, platform `admin.py` | Rotates token; email wired on latest branch |
| Member invite | `provision_user_invitation()`, `org_admin.py` | Link only |
| Employee join | `employee_join.py`, `JoinOrgPage.tsx` | Verification code in DB hash; email stub |
| Admin accept | `admin_invitation_accept.py`, `AcceptInvitePage.tsx` | 6-digit code, 15m TTL (now 10m) |
| Password reset | `password_reset.py` | Stub reset email |

### Flows that send email (Step C)

1. Organization admin invitation (create + resend + “Resend email” in history)
2. Member invitation (org admin invites user by email)
3. Verification codes — admin invitation accept, employee join, extensible for signup/email change
4. Password reset
5. Employee welcome (after approval/auto-approve)

Templates live in **`backend/app/services/email/templates.py`** (HTML + plain text in code). Brevo template IDs are not required; you can add `BREVO_TEMPLATE_*` env vars later if you move templates into Brevo.

---

## Step F — Manual checklist

1. Create a [Brevo](https://www.brevo.com/) account and generate an **API v3 key**.
2. Verify **sender** (`EMAIL_FROM_ADDRESS`) or authenticate your domain (SPF, DKIM, DMARC).
3. Set environment variables on the API host (never commit secrets):

```env
EMAIL_PROVIDER=brevo
BREVO_API_KEY=your-key
EMAIL_FROM_ADDRESS=noreply@yourdomain.com
EMAIL_FROM_NAME=AQREM
PUBLIC_APP_URL=https://your-app.example
```

For Azure Container Apps, store `BREVO_API_KEY` in secrets and map the rest as env vars.

### Brevo “unrecognised IP address” (401)

If `email_delivery_logs.error_message` mentions an **unrecognised IP**, Brevo’s **Authorized IPs** allowlist is blocking your API server (e.g. Tailscale exit, home ISP, or Azure outbound IP).

1. Open [Brevo → Security → Authorized IPs](https://app.brevo.com/security/authorised_ips).
2. Either **add the public IP** shown in the error (the IP Brevo sees when `aqrem-api` calls their API — often your home/Azelos WAN IP, not `100.x` Tailscale), **or** disable IP restriction for API access if your account policy allows it.
3. Retry: `python ../scripts/send_test_email.py you@example.com` and check `email_delivery_logs.status` becomes `sent`.

Until this is fixed, verification and invitation emails will stay **`failed`**; the AQREM app cannot override Brevo account security.

4. Test:

```bash
cd backend
EMAIL_PROVIDER=console APP_ENV=development python ../scripts/send_test_email.py you@example.com
# or with Brevo configured:
python ../scripts/send_test_email.py you@example.com
```

5. Recreate the API container after changing env: `bash scripts/restart-api-docker.sh`

---

## Development providers

| `EMAIL_PROVIDER` | When |
|------------------|------|
| *(empty)* + legacy `EMAIL_DELIVERY_MODE=log` | Dev: **console**; production: **none** |
| `console` | Prints email metadata + text preview to API logs (**dev only**, explicit) |
| `brevo` | Brevo HTTP API (required in production if you enable email) |
| `none` | No sends |

Production **rejects** `EMAIL_PROVIDER=console` at startup. With `EMAIL_PROVIDER=brevo`, startup requires `BREVO_API_KEY` and `EMAIL_FROM_ADDRESS`.

---

## Delivery log

Table **`email_delivery_logs`**: type, recipient, status (`queued` / `sent` / `failed`), provider message id, error (no bodies or codes). Super Admin **Invitation history** shows `email_delivery_status` and errors.

---

## Verification policy

- 6-digit codes, **SHA-256 hash** stored only
- **10 minute** expiry, single use
- **5** failed attempts then code invalidated
- Send rate limit: **1 / 60s** per invitation (`last_verification_code_sent_at`) and **5 successful sends / hour** per recipient (Brevo `sent` rows only). Failed sends do not count toward the hourly cap.

If you hit **429** while testing, wait 60 seconds or clear `user_invitations.last_verification_code_sent_at` for that invite in Postgres.

---

## Optional Brevo webhooks

Not implemented in MVP; add a signed `POST /api/v1/webhooks/brevo` later to map `delivered` / `bounced` into `email_delivery_logs.status`.
