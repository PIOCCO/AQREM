# Gateway fail-open / degraded mode (control-plane DB outage)

Environment variables (see `app/config.py`):

| Variable | Default | Meaning |
|----------|---------|---------|
| `KEY_VALIDATION_CACHE_SECONDS` | 60 | Keys **already validated** keep working without DB for this window |
| `KEY_REVOKE_MAX_SECONDS` | 60 | Revoked keys stop within this window (cache TTL capped to this) |
| `LIMIT_DB_STALE_SECONDS` | 120 | After DB down this long, switch to **degraded** limits (not hard fail) |
| `OUTAGE_CONSERVATIVE_RPM` | 10 | Degraded RPM cap per client |
| `OUTAGE_CONSERVATIVE_TPM` | 5000 | Degraded TPM cap |
| `OUTAGE_CONSERVATIVE_MONTHLY_BUDGET` | 100000 | Degraded monthly token cap when budget cache is stale |

## Behavior

1. **DB up:** full DB auth + limits flush.
2. **DB down (0–N seconds):** cached validations honored; unknown keys **401**; last known limits + local counters; monthly budget from cache.
3. **DB down (> N seconds):** **degraded** conservative limits; alert via App Insights logs (`gateway degraded=1` — wire alert in ops); auto-recover when DB queries succeed again.

Tests: `infra/model-gateway/tests/test_failopen.py`.
