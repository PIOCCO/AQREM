# Offline licensing (dedicated environments)

Dedicated environments (`DEPLOYMENT_MODE=dedicated`) check an **offline, signed license**; nothing is
sent anywhere. Shared mode does not use it (per-organization seats, `license_limit`, remain as before).

Code: `backend/app/services/offline_license.py` (authenticity + applicability),
`backend/app/services/license_enforcement.py` (warning / grace / read-only), operator tool
`scripts/aqrem_license.py`.

## License file
```json
{"payload": {"license_id": "…uuid…", "organization": "Contoso", "organization_slug": "contoso",
             "environment": "contoso", "deployment_mode": "dedicated", "seats": 50, "features": [],
             "issued_at": "2026-10-17T10:00:00Z", "not_before": "2026-11-01T00:00:00Z",
             "expires_at": "2027-10-31T23:59:59Z", "grace_days": 14, "version": 2},
 "signature": "<base64 Ed25519 over the canonical JSON of payload>", "alg": "Ed25519"}
```
* **Every payload field is signed** (canonical JSON: sorted keys, no whitespace). Changing, adding or removing
  any field — seats, dates, slug, environment, even `"5"` vs `5` — invalidates it. Re-formatting the file
  (indentation, key order) does not.
* Required: `license_id, organization, organization_slug, environment, deployment_mode, seats (>0),
  issued_at, expires_at` (UTC, `Z`). Optional: `not_before`, `grace_days` (0–90, default 14), `features`.
* **Binding**: `deployment_mode` must be `dedicated`, `environment` must equal the environment's
  `ENVIRONMENT_NAME`, `organization_slug` the dedicated organization's slug. Terraform sets both
  `ENVIRONMENT_NAME` and `DEDICATED_ORG_SLUG` to the client id, so use the client id for both.
* Installed as Key Vault secret `license-key` (loaded into the api as `LICENSE_KEY` at start) or a file
  (`LICENSE_FILE`). Format version 1 licenses (no environment/slug binding) are no longer accepted.

## What customers see
| Level | When | Effect | Message (organization admins) |
|---|---|---|---|
| `ok` | valid, within seats | everything works, no banner | — |
| `warning` | valid but expires in < 30 days, **or** the server clock went backwards | everything works; amber banner for admins | "The license expires on DATE (N days left)…" / clock notice |
| `grace` | expired < `grace_days` ago; or more users than seats (since first detected); or license missing/invalid/for another environment on an environment that **was** licensed before (14 days since first detected) | everything works; amber banner for admins. Adding users: allowed within seats while only *expired*; refused while seats are exceeded or the license is unreadable | what is wrong + "All features remain available until DATE; after that AQREM switches to read-only mode." |
| `read_only` | after the grace period; or no valid license was ever installed (fresh environment) | red banner for everyone. Sign-in, reading, search, exports, admin settings, deactivating users, deleting documents keep working. **Refused** (`403`, `code: LICENSE_READ_ONLY`): uploads, chat questions, new chat shares, projects, questionnaires, sources, re-indexing, inviting/approving/accepting users | what is wrong + "AQREM is in read-only mode: existing content, search, exports and administration remain available; new uploads, chats and users are blocked. No data is deleted." |

Non-admin users only ever see: "AQREM is currently in read-only mode for this organization. Existing content
remains available. Please contact your administrator." (`GET /api/v1/license/status` returns details only to
organization admins.) Messages say what is wrong and to contact the vendor; they never mention keys, file
locations or settings. Operators get a reason code in the api log
(`license enforcement: level=… code=… reason=signature_invalid|format_invalid|fields_invalid|environment_mismatch|organization_mismatch|mode_mismatch|not_yet_valid|expired|missing`).

**No license state ever deletes or modifies customer data**; read-only only refuses new writes. Sign-in
no longer depends on the license in dedicated mode (before this change an invalid license blocked all sign-in).
Read-only is enforced by the api (deny-by-default for every non-GET route under `/api/v1` except a short
allowlist in `license_enforcement._READ_ONLY_ALLOWED`; a test fails if the allowlist references a route that
no longer exists). Jobs already queued in the worker finish.

## Seats
A seat = an **active membership of an active user** in the organization, plus pending (unused, unrevoked,
unexpired) invitations and pending employee-join requests. Deactivated memberships and deactivated user
accounts do not count. At the limit: no new users (invite/accept/approve refused with a clear message);
existing users keep working. Above the limit (e.g. a renewal with fewer seats): `grace`, then `read_only`
until enough users are deactivated or a license with more seats is installed.

## Time and clock rollback
All license decisions use `max(system clock, highest time ever recorded by this environment, license issue
time)`. The highest time is persisted in `license_runtime_state` (migration 7; the app role cannot delete the
row). Setting the clock back therefore never makes an expired license valid or extends a grace period. If the
clock is more than 2 hours behind the recorded time (or behind the license issue time) the admins see:
"The server clock is behind the last time recorded by this environment… check the server's time
synchronisation." The flag clears when the clock catches up. Small skews between replicas are tolerated.

## Operator: issue a license
On the machine that holds the signing key (offline / vault; **never** on a shared server, never committed —
`scripts/check_secrets.py` flags private keys):
```bash
python3 scripts/aqrem_license.py sign --key /secure/aqrem-license-private.pem \
  --org "Contoso Ltd" --slug contoso --environment contoso --seats 50 --expires 2027-10-31 \
  [--not-before 2026-11-01] [--grace-days 14] [--features chat,questionnaires] --out contoso.license.json
python3 scripts/aqrem_license.py verify --license contoso.license.json --slug contoso --environment contoso
# (verify uses the keys embedded in the checked-out code; add --public-key <b64> to check against another key)
```
Install and activate:
```bash
az keyvault secret set --vault-name <kv> -n license-key --file contoso.license.json -o none
REV=$(az containerapp show -n contoso-api -g rg-aqrem-contoso --query properties.latestRevisionName -o tsv)
az containerapp revision restart -n contoso-api -g rg-aqrem-contoso --revision "$REV"
```
Check: org admin → banner gone; `GET /health` → `license.status = valid`. The license file is not secret
(it is signed, not encrypted) but contains the customer name/seat count; send it like any contract document.

## Operator: renew / change seats / replace
Issue a new license (new `license_id`, new dates/seats) **before** the old one expires and install it as above.
Renewing during `grace` or `read_only` restores full service immediately after the api restart. A license for
fewer seats than in use starts the seat grace period.

## Operator: production signing key (the embedded key is a DEVELOPMENT key)
The image currently trusts only `dev-2026-10` (`EMBEDDED_PUBLIC_KEYS` in `offline_license.py`); its private
key lives on a development box. Before the first real customer:
1. On an offline machine (no network, full-disk encryption):
   `python3 scripts/aqrem_license.py keygen --out-dir /media/secure/aqrem-license-prod`
   (writes `aqrem-license-private.pem` mode 0600 and prints the public key). Keep the private key offline
   (encrypted USB in a safe + a second copy, or a vault/HSM-backed secret store with two-person access).
   It is never needed by an environment.
2. Add the printed public key to `EMBEDDED_PUBLIC_KEYS` as e.g. `"prod-2026-11": "<b64>"`, remove
   `dev-2026-10` from production builds (decision: keep a separate dev build, or keep both for one release),
   commit, build and roll out images (`scripts/rollout-dedicated.sh`).
3. Re-issue every customer license with the production key and install it (before removing the old key).
4. Rotation later: add the new key next to the old one for one release, re-issue licenses, then remove the old
   key. Compromised key: ship an image without it and re-issue all licenses immediately.

`LICENSE_PUBLIC_KEY` (a verification-key override) exists only for automated tests and is ignored unless
`APP_ENV` is `development` or `test` (the images set `APP_ENV=production`; Terraform sets it too). Grace and
warning periods are code constants or signed license fields, not settings. `LICENSING_TEST_MODE` (shared tier)
is forced off in production.

## Limits (honest)
An offline license is a deterrent and an integrity check, not DRM: whoever controls the image, the
environment variables (e.g. sets `APP_ENV=development` and an override key) or the database owner role
(e.g. rewrites `license_runtime_state`) can defeat it. In AQREM-hosted dedicated environments those are
operator-only. Customer-hosted deployments would need more (signed images, attestation) — not implemented.
