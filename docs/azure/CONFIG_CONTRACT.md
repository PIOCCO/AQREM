# Azure client deployment — configuration contract (Stage 4)

All model traffic uses the **custom model gateway** (not direct Azure OpenAI from app containers).

## API and worker (runtime)

| Variable | Required (production) | Purpose |
|----------|----------------------|---------|
| `LLM_PROVIDER` | yes | Must be `gateway` in production |
| `GATEWAY_URL` | yes | Base URL of the client model gateway (private) |
| `GATEWAY_API_KEY` | yes* | Platform fallback key; per-org keys may also be stored in Key Vault |
| `GATEWAY_CHAT_ALIAS` | no (default `chat-default`) | Chat path alias |
| `GATEWAY_EMBEDDINGS_ALIAS` | no (default `embeddings-default`) | Embeddings path alias |
| `GATEWAY_TIMEOUT_SECONDS` | no (default `120`) | Upstream request timeout |
| `EMBEDDING_DIMENSIONS` | yes | Must match gateway embedding deployment dimension |

\* Org-specific gateway keys are minted via control-plane onboarding and stored in client Key Vault; the app resolves per-organization keys when present.

## Gateway HTTP contract (app → gateway)

- `POST {GATEWAY_URL}/v1/chat-default/chat/completions` — chat (JSON or SSE when `stream: true`)
- `POST {GATEWAY_URL}/v1/embeddings-default/embeddings` — embeddings
- Auth: `Authorization: Bearer <key>` or `X-AQREM-Gateway-Key`
- `429` responses include `Retry-After` and JSON `code`: `rate_limit_exceeded` or `monthly_token_budget_exceeded`
- `401` invalid key — do not retry

## Web (build-time)

| Variable | Required (production) |
|----------|----------------------|
| `VITE_PUBLIC_APP_URL` | yes — must match `PUBLIC_BASE_URL` / `APP_PUBLIC_BASE_URL` |

## Smoke check

From repo root after deploy:

```bash
LLM_PROVIDER=gateway GATEWAY_URL=... GATEWAY_API_KEY=... python3 scripts/verify_model_integration.py
```

See also `infra/terraform/docs/GATEWAY_CLIENT_BEHAVIOR.md`.
