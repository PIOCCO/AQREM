# Azure OpenAI setup (chat answers + embeddings)

AQREM uses **one** setting, `LLM_PROVIDER`, to choose the provider for **both** chat answers and
embeddings. `azure` is the default in `docker-compose.local-prod.yml` (the Raspberry Pi stack).
`mock` (deterministic local placeholder) is for development and tests only. The API and worker
refuse to start with it when `APP_ENV=production`.

When you're done here you only need to: create the Azure resources, fill `.env`, then rebuild and restart.
No code changes are needed.

---

> **Prefer Terraform.** `infra/terraform/` (with `envs/dev.tfvars` / `envs/prod.tfvars`) creates the
> account and both deployments reproducibly, and outputs the non-secret env values
> (`terraform output aqrem_backend_env`). See [`docs/azure-terraform.md`](azure-terraform.md) for the
> runbook, the model availability and retirement notes, and costs. Note: in swedencentral
> `text-embedding-3-small` is only offered as *Global Standard* or *Data Zone Standard*, not regional *Standard*.
> The portal steps below are the manual equivalent.

## 1. Create the Azure resources

1. **Azure portal → Create a resource → "Azure OpenAI"**
   - Subscription / resource group: any (e.g. `rg-aqrem`).
   - **Region**: pick one that offers both `gpt-4o-mini` and `text-embedding-3-small`
     (e.g. Sweden Central, East US 2, France Central). If a model is missing in your region, the
     "Test AI connection" button reports *unsupported model / wrong region*.
   - Name: e.g. `aqrem-openai` (this becomes `https://aqrem-openai.openai.azure.com/`).
   - Pricing tier: Standard S0.
2. **Open the resource → "Go to Azure AI Foundry portal" → Deployments → Deploy model → Deploy base model**
   - **Chat deployment**: model `gpt-4o-mini`, deployment name e.g. **`aqrem-chat`**,
     type *Standard* (or *Global Standard*), set tokens-per-minute (TPM) to at least 30K.
   - **Embedding deployment**: model `text-embedding-3-small`, deployment name e.g.
     **`aqrem-embeddings`**, TPM at least 100K is comfortable for indexing.
   - Deployments can take 1 to 5 minutes before they answer. Until then you get *DeploymentNotFound*.
3. **Resource → Resource Management → Keys and Endpoint**: copy **Endpoint** and **KEY 1**.

## 2. Fill `.env` (repo root, gitignored, never commit it)

| Azure value | Env var | Example |
|---|---|---|
| Provider for chat + embeddings | `LLM_PROVIDER` | `azure` |
| Keys and Endpoint → Endpoint | `AZURE_OPENAI_ENDPOINT` | `https://aqrem-openai.openai.azure.com/` |
| Keys and Endpoint → KEY 1 | `AZURE_OPENAI_API_KEY` | *(secret)* |
| API version | `AZURE_OPENAI_API_VERSION` | `2024-10-21` |
| Chat **deployment name** (not model name) | `AZURE_OPENAI_CHAT_DEPLOYMENT` | `aqrem-chat` |
| Embedding **deployment name** | `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | `aqrem-embeddings` |
| Vector size of the embedding model | `EMBEDDING_DIMENSIONS` | `1536` (text-embedding-3-small) |
| Optional: max answer tokens | `LLM_MAX_ANSWER_TOKENS` | `1024` |
| Optional: temperature (keep low) | `LLM_TEMPERATURE` | `0.1` |
| Optional: retries on 429/5xx | `LLM_MAX_RETRIES` | `3` |
| Optional: send dimensions param | `AZURE_OPENAI_EMBEDDING_SEND_DIMENSIONS` | `true` (`false` for ada-002) |

```dotenv
LLM_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://aqrem-openai.openai.azure.com/
AZURE_OPENAI_API_KEY=<KEY 1>
AZURE_OPENAI_API_VERSION=2024-10-21
AZURE_OPENAI_CHAT_DEPLOYMENT=aqrem-chat
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=aqrem-embeddings
EMBEDDING_DIMENSIONS=1536
```

### Keyless option: Microsoft Entra ID (managed identity)

The app supports `AZURE_OPENAI_USE_MANAGED_IDENTITY=true` (it then uses `DefaultAzureCredential` and
ignores `AZURE_OPENAI_API_KEY`). Give the app's identity the **Cognitive Services OpenAI User** role on
the account (Terraform: `managed_identity_principal_id`). The production Terraform env also sets
`local_auth_enabled = false`, so keys stop working there.

Managed identity **only works when AQREM runs inside Azure** (Container Apps, App Service, VM).
The **Raspberry Pi can't use it**. On the Pi, keep `AZURE_OPENAI_API_KEY` in the gitignored `.env`
(`chmod 600 .env`), and point it at an account with `local_auth_enabled = true` (the dev env).
Fetch the key with `az cognitiveservices account keys list` (see `docs/azure-terraform.md` §6). Don't use a Terraform output.
A service principal secret (`AZURE_CLIENT_ID`/`AZURE_TENANT_ID`/`AZURE_CLIENT_SECRET` read by
`DefaultAzureCredential`) also works off-Azure, but it is still a secret stored on the device.

Calls always use the **deployment names** from env. Model names are never sent.
`docker-compose.local-prod.yml` passes all of these into the `api`, `worker` and `worker-beat`
containers.

## 3. Embedding size and the database (read this if you used mock/OpenAI before)

Indexing and querying use the **same** embedding deployment and `EMBEDDING_DIMENSIONS`. The DB column
`evidence_items.embedding` is `vector(N)`. N must equal `EMBEDDING_DIMENSIONS`.

At startup the API compares them. When they differ it logs (and in production refuses to start with):

```
EMBEDDING DIMENSION MISMATCH: Database column evidence_items.embedding is vector(384) but EMBEDDING_DIMENSIONS=1536. ...
```

### Changing the embedding size (e.g. 384 → 1536)

```bash
cd ~/AQREM                                   # your checkout on the Pi
docker compose -f docker-compose.local-prod.yml up -d postgres
scripts/migrate-embedding-dimensions.sh 1536  # ALTER ... TYPE vector(1536) USING NULL (clears old vectors)
# if an organization uses its own tenant database, run it for that DB too:
#   DB_NAME=<tenant_db> scripts/migrate-embedding-dimensions.sh 1536
```

Equivalent SQL:

```sql
ALTER TABLE evidence_items ALTER COLUMN embedding TYPE vector(1536) USING NULL;
ALTER TABLE answer_library_entries ALTER COLUMN question_embedding TYPE vector(1536) USING NULL;
```

Then rebuild/restart (section 4) and in **Admin → Documents** click **Re-index all documents**
(API: `POST /api/v1/org-admin/documents/reindex-all`).

Each document stores the embedding deployment and vector size it was indexed with
(`client_documents.embedding_model`, `client_documents.embedding_dimensions`). When you switch
deployment or size, the Documents page shows a warning and the affected rows say *"Indexed with a
different embedding model or size"*. Until you re-index, those chunks are still found by keyword
search, so results never silently drop to nothing.

## 4. Rebuild and restart on the Raspberry Pi

```bash
cd ~/AQREM            # path of your checkout
git fetch origin && git checkout azure-openai-final && git pull
nano .env             # fill the values from section 2
docker compose -f docker-compose.local-prod.yml build api worker worker-beat
docker compose -f docker-compose.local-prod.yml up -d --force-recreate api worker worker-beat
# web UI (new "Test AI connection" / "Re-index all documents" buttons):
docker compose -f docker-compose.local-prod.yml build web && docker compose -f docker-compose.local-prod.yml up -d web
```

If you only changed `.env` (no code change), you don't need to rebuild. Run only:
`docker compose -f docker-compose.local-prod.yml up -d --force-recreate api worker worker-beat`.

## 5. Confirm the active provider

- **Log line** (no secrets):
  ```bash
  docker compose -f docker-compose.local-prod.yml logs api worker | grep "Active providers"
  # Active providers: role=api llm=azure chat_model=azure:aqrem-chat embeddings=azure
  #   embedding_model=azure:aqrem-embeddings:1536 dimensions=1536 endpoint_host=aqrem-openai.openai.azure.com auth=api_key
  ```
- **Health endpoint**: `curl -s http://127.0.0.1:8000/health/ready | python3 -m json.tool` shows
  `"llm": {"provider": "azure", "chat_deployment": ..., "embedding_deployment": ..., "configured": true}`.
- **UI**: Admin → Documents → **Test AI connection** sends one tiny chat and one tiny embedding request.

## 6. Troubleshooting (what "Test AI connection" tells you)

| Message | Cause / fix |
|---|---|
| *Wrong key (HTTP 401)* | `AZURE_OPENAI_API_KEY` is not from the same resource as the endpoint. |
| *Wrong endpoint: host could not be resolved (DNS)* / *HTTP 404* | Typo in `AZURE_OPENAI_ENDPOINT`. Use `https://<name>.openai.azure.com/` with nothing after the host. |
| *Deployment not found (DeploymentNotFound)* | Deployment name typo (use the deployment name, not the model name), or it was created less than 5 minutes ago. |
| *Rate limit / Quota exceeded (HTTP 429)* | Raise the deployment's TPM quota. Requests are retried automatically, honouring `Retry-After`. |
| *Unsupported model / region* | Chat deployment must be a chat model and embedding deployment an embedding model, in a region that offers them. |
| *Embedding size mismatch* | `EMBEDDING_DIMENSIONS` does not match the model. See section 3. |

Startup with a missing value fails fast and names the variable. It never prints the value. Example:

```
RuntimeError: LLM_PROVIDER=azure but Azure OpenAI is not fully configured. Missing: AZURE_OPENAI_API_KEY or AZURE_OPENAI_USE_MANAGED_IDENTITY=true. Set these in your .env file (see .env.example and docs/azure-openai-setup.md), then rebuild/restart the api and worker containers.
```

Employees never see raw provider errors. They see *"The assistant is temporarily unavailable,
please try again."* The real error is logged in the `api` container. If indexing fails, the document
is marked **failed** with a readable reason (e.g. *Indexing failed: Deployment not found ...*). It is
never shown as indexed.

## 7. Answer grounding

The system prompt gives the model only the retrieved document chunks (with document name and page).
It tells the model to answer only from them, to say *"I couldn't find this in the available documents"*
when the answer isn't there, and never to invent facts. Every grounded answer ends with
`Sources: <document>, p. <page>` (pages are recorded for PDFs at indexing time).
