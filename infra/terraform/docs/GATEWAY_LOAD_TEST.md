# Gateway load test (RPM/TPM hot path)

## Goal

Measure latency overhead and control-plane PostgreSQL load when enforcing RPM/TPM with **hybrid per-replica counters + periodic DB flush**, at:

1. **Realistic peak** (configure from expected clients × RPM)
2. **5× peak** (stress)

## Tooling

Script: `infra/model-gateway/load/k6-gateway.js`

```bash
export GATEWAY_URL=https://<gateway-fqdn>
export GATEWAY_API_KEY=gw_...
k6 run infra/model-gateway/load/k6-gateway.js
```

Env overrides:

- `K6_VUS` (default 50)
- `K6_DURATION` (default 5m)
- `K6_STREAM=1` for SSE chat completions

## Architecture under test

- **Hot path:** in-memory minute windows per replica (`LimitEngine`); optional DB upsert to `gateway.rate_window` (best-effort).
- **Monthly budget:** reconciled from `gateway.usage_daily` on hydrate and after usage writes; fail closed on budget when cache is fresh.
- **Fail-safe:** if control-plane PG is unavailable, serve up to **`LIMIT_DB_STALE_SECONDS`** (default **120s**) using last known limits (documented inaccuracy up to ~**5–10%** over RPM/TPM across replicas until DB recovers).

## What to record (paste into this doc after running in DEV)

| Scenario | VUs | p50/p95 latency | PG CPU / connections | 429 rate | Notes |
|----------|-----|-----------------|------------------------|----------|-------|
| Realistic peak | | | | | |
| 5× peak | | | | | |

## Decision criteria

- If p95 adds **>25ms** vs no-limit baseline **or** PG becomes the bottleneck → keep in-memory primary path (current default) and widen flush interval slightly.
- If inaccuracy exceeds product tolerance → reduce flush interval or add Redis (deferred v1).

## Results (2026-10-14 agent run)

| Scenario | VUs | Duration | p50 (ms) | p95 (ms) | Requests | Notes |
|----------|-----|----------|----------|----------|----------|-------|
| Realistic peak | 50 | 30s | *blocked* | *blocked* | — | Agent VM: **no Docker/k6/Azure**; use `docker-compose.loadtest.yml` + `load/k6-gateway.js` in DEV |
| 5× peak (stream) | 250 | 30s | *blocked* | *blocked* | — | Same |

**Verified in agent:** unit tests for fail-open/degraded limits (`test_failopen.py`); hybrid limit engine under mock upstream.

**You must run in DEV** (compose or deployed gateway) and paste k6 summary before Stage 4. Commands:

```bash
cd infra/model-gateway
docker compose -f docker-compose.loadtest.yml up -d --build
# seed gateway.client + api_key in cp-postgres, then:
export GATEWAY_URL=http://localhost:8088 GATEWAY_API_KEY=gw_...
K6_VUS=50 K6_DURATION=5m K6_STREAM=1 k6 run load/k6-gateway.js
K6_VUS=250 K6_DURATION=5m K6_STREAM=1 k6 run load/k6-gateway.js
```
