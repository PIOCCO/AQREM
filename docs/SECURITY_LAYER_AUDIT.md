# Security findings — layer link audit

## Fixed in this audit

| Severity | Finding | Fix |
|----------|---------|-----|
| Major | Tenant JWT could call L1 master routes if user flag set | `require_platform_admin` rejects tokens with `organization_id` or wrong `aud` |
| Major | Master/employee tokens could hit L3 data plane | `get_tenant_context` rejects `aqrem-master` / `PLATFORM_ADMIN` |
| Major | Accept-invite tokens missing `aud` | Set `aqrem-org-admin` / `aqrem-employee` on accept |
| Major | Deactivated member JWT still valid until expiry | `membership.auth_version` in JWT; bump on deactivate |
| Major | L2 telemetry never reached L1 store | `ingest_org_telemetry` on token save, upload, invite |
| Major | Seat math double-counted invite + membership | Pending invites skip rows with active membership |
| Minor | Stale `license_limit` on invite after L1 PATCH | `db.refresh(org)` in `assert_can_add_seat` |
| Minor | `Role.PLATFORM_ADMIN` crash on invite | Compare role string instead |

## Open (not fixed — requires infra or larger scope)

| Severity | Finding | Reason |
|----------|---------|--------|
| Blocker | Per-tenant model token not used by L3 chat/LLM | `get_llm_provider()` is global; needs tenant-aware factory + Azure KV |
| Blocker | Azure Key Vault adapter stub in production | Real deployment credential + managed identity |
| Major | No mTLS / managed-identity S2S between hosts | Monolithic app; split deploy not in repo |
| Major | JWT `verify_aud` disabled globally | Layer checks added manually; full aud verification TODO |
| Major | No org hard-delete / key revocation pipeline | Suspend-only offboarding |
| Major | Break-glass support access | Not implemented (documented) |
| Major | L1 UI missing provision/health/telemetry views | API exists; UI dead links |
| Minor | No signed webhooks / DLQ | No webhook handlers |
| Minor | S10 kill-switch drills | Not automated (manual infra) |
| Minor | S6 delete document → RAG purge | Needs e2e with worker + embedding delete test |

## Automated scenarios (local PostgreSQL)

| Scenario | Result | Test |
|----------|--------|------|
| S1 Provision org + URLs | Pass | `test_s1_provision_and_telemetry_pipeline` |
| S2 Seats full → raise limit | Pass | `test_s2_seat_limit_then_raise` |
| S3 Suspend → L3 blocked | Pass | `test_s3_license_suspend_blocks_l3` |
| S4 Remove employee → session dead | Pass | `test_s4_deactivate_revokes_session` |
| S5 Token rotate | Not run end-to-end | LLM not tenant-bound |
| S6 Document delete RAG | Not run | worker e2e gap |
| S7 Two tenants | Pass | `test_s7_two_tenant_isolation` |
| S8 Token confusion | Pass | `test_s8_token_confusion_matrix` |
| S9 Telemetry injection | Pass | `test_s9_*`, existing telemetry tests |
| S10–S11 Kill / offboard | Not run | requires multi-service env |
| S12 IDOR/JWT pentest | Partly | `test_e2e_authorization`, `test_security_tenant_matrix` |

**Full backend run:** `112 passed` (`python3 -m pytest tests/backend/`).

## GO / NO-GO for real customers

**NO-GO** for production multi-tenant SaaS until blockers closed.

**Top 5 risks**

1. Chat/RAG does not use customer model tokens from Key Vault (wrong compliance story).
2. Azure provisioning and secret store are stubs — production deploy may be `blocked`.
3. No cryptographic audience enforcement on every JWT decode path.
4. Offboarding is suspend-only; no guaranteed data/key erasure workflow.
5. Monolith deployment — L1/L2/L3 separation on network/host is operational, not enforced in code.

**GO** for controlled pilot/lab on single deployment with in-memory secret store, test orgs, and explicit customer communication about above limits.
