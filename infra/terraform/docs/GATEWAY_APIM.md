# Model gateway: custom now, APIM later

## Current (v1)

- **`modules/model_gateway_custom`** — Container App (`infra/model-gateway/`), min **2** replicas.
- Clients call **`GATEWAY_URL`** + per-client key (`GATEWAY_API_KEY` from client Key Vault).
- OpenAI access via **gateway MI only**; deployment aliases **`chat-default`** / **`embeddings-default`**.

## Revisit APIM when

Set **`enable_apim=true`** (and likely **`enable_custom_gateway=false`**) if any of:

| Trigger | Why APIM |
|---------|----------|
| **>30–50 clients** and gateway ops toil | Built-in products/subscriptions, less custom code |
| **Developer portal / external API products** | APIM developer portal |
| **Compliance** requires managed API gateway with formal SLA | Standard v2 SLA ~99.95% |
| **Advanced monetization** | Native subscription + quota policies (incl. `llm-token-limit` on v2) |

APIM **Consumption** remains **unsuitable** for AQREM (no SSE, 30s limit, no token policies) — use **Standard v2** (~**$700/mo/unit**, [pricing](https://azure.microsoft.com/pricing/details/api-management/)).

Migration: point `GATEWAY_URL` at APIM; keys become APIM subscription keys; apps unchanged.
