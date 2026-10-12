# Azure OpenAI integration

AQREM uses **Azure OpenAI** for embeddings (ingestion + retrieval) and structured answer generation (questionnaires). The backend never exposes credentials to the browser.

## SDK and API

- Provider: `app.services.llm.azure_openai.AzureOpenAIProvider`
- Client: official **`openai`** Python package (`AsyncAzureOpenAI`)
- Chat: deployment chat completions with `response_format: json_object`
- Embeddings: deployment embeddings API

## Environment variables

| Variable | Purpose |
|----------|---------|
| `LLM_PROVIDER` | `mock` (local/CI default) or `azure` |
| `AZURE_OPENAI_ENDPOINT` | Resource endpoint, e.g. `https://<name>.openai.azure.com` |
| `AZURE_OPENAI_API_KEY` | Local/dev key (omit when using managed identity) |
| `AZURE_OPENAI_USE_MANAGED_IDENTITY` | `true` for Entra ID / managed identity in Azure |
| `AZURE_OPENAI_API_VERSION` | e.g. `2024-10-21` |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | Chat deployment **name** (not model name) |
| `AZURE_OPENAI_DEPLOYMENT` | Alias for chat deployment name |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | Embedding deployment name |
| `EMBEDDING_DIMENSIONS` | Must match pgvector column (384 mock, **1536** for `text-embedding-3-small`) |

Terraform in `infra/terraform/openai.tf` provisions the Azure resource and deployments; copy deployment names into the variables above.

## Behavior

- **`LLM_PROVIDER=azure`**: Azure provider is required; incomplete config raises at startup (production) or when the provider is first used.
- **`LLM_PROVIDER=mock`**: Deterministic hash embeddings and evidence-only draft answers (CI/local without Azure).
- Retries: bounded retries on rate limits, timeouts, and connection errors.
- Guardrails: evidence sanitized before prompts; citation IDs validated against retrieval results (`app/services/llm/guardrails.py`).

## Health

- `GET /health/live` — process up
- `GET /health/ready` — database connectivity + LLM configuration summary (503 if DB down or Azure incomplete when `LLM_PROVIDER=azure`)

## Live smoke test (optional)

Only when you have a configured Azure resource:

```bash
export LLM_PROVIDER=azure
export AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
export AZURE_OPENAI_API_KEY=<your-key>
export AZURE_OPENAI_CHAT_DEPLOYMENT=<chat-deployment>
export AZURE_OPENAI_EMBEDDING_DEPLOYMENT=<embedding-deployment>
python3 scripts/azure_openai_smoke.py
```

**Verified status:** run the smoke script in your environment to mark live Azure connectivity as verified. CI uses mocks only.

## Cost note

Embedding every chunk and generating answers consumes Azure OpenAI quota. Use separate deployments and capacity limits in Terraform; monitor usage in Azure Portal.
