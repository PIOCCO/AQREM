# Client app behavior when the model gateway fails

The gateway is a **shared dependency**. Client API/worker should:

## HTTP status handling

| Status | Meaning | Client action |
|--------|---------|----------------|
| **429** | Rate limit or monthly budget | Honor `Retry-After`; backoff (exponential, cap 60s); show user “High demand, retry shortly” |
| **401** | Invalid/missing gateway key | Do not retry; alert ops (key rotation / config) |
| **5xx** | Gateway or upstream error | Retry idempotent requests with jittered backoff (3–5 attempts); degrade chat UI with clear message |
| **Timeout** | No response in upstream window | Treat as 5xx; retry once for streaming if safe |

## Configuration

- Read gateway base URL and key from **client Key Vault** (never bake into images).
- Support **two active keys** during rotation (primary/secondary).

## Observability

- Log gateway status, latency, and `clientId` correlation id.
- Platform alert: gateway 5xx rate (see `RUNBOOK.md` → Gateway alerts).
