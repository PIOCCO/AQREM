# Azure verification (October 2026)

Sources: Microsoft Learn, Azure pricing pages, and Terraform provider docs checked during Phase 3 Stage 1 design. Re-verify before production apply.

## D3 — Container Apps cells

| Check | Result (Oct 2026) |
|-------|-------------------|
| Apps per environment | **No fixed app count quota.** Limiting factor is **consumption cores per managed environment** (default often **40**, increase via quota request up to **~100**). |
| Replicas | Default **30 replicas per revision** (quota increase possible). **Max 2 cores per replica** (consumption). |
| Environments per subscription/region | **Managed Environment Count** quota (subscription + region; global cap may block before regional display shows headroom). Request increases for prod scale. |
| 3 apps × 100 clients | **300 apps in one environment is allowed** if core quota allows. At ~0.5–1.0 active cores per client (3 apps, scale-to-zero worker), **100 clients ≈ 50–100+ cores** → **plan multiple cells**, not one default 40-core environment. |

**Recommended cell sizing (initial):**

- **Starter/Standard cell:** target **≤25 clients** per shared environment (≈25–40 cores headroom at default 40-core quota).
- **Control plane** picks cell with `remaining_cores >= required_cores(plan)`; Business clients **never** share a cell (dedicated environment).

**Cross-app calls in same environment:** Apps with **internal ingress** are reachable from other apps via **`http://<app-name>`** or internal FQDN ([Connect apps](https://learn.microsoft.com/en-us/azure/container-apps/connect-apps)). **Mitigation:** API/worker **internal only**; only **web** external; **Entra JWT** on all API routes; optional **mTLS / shared secret** for internal calls; **no client A env vars pointing to client B hostnames** (provisioned from control plane only).

## D4 — Model gateway (APIM Consumption conditional)

| Requirement | APIM Consumption | Verdict |
|-------------|------------------|---------|
| Per-subscription **token quota** (`llm-token-limit`) | **Not supported** on Consumption ([policy matrix](https://learn.microsoft.com/en-us/azure/api-management/api-management-policies)) | Fail |
| **Token metrics** (`emit-llm-token-metrics`) | **Not supported** on Consumption | Fail |
| **Streaming / SSE** | **Not supported**; long-running HTTP not supported on Consumption ([SSE doc](https://learn.microsoft.com/en-us/azure/api-management/how-to-server-sent-events)) | Fail |
| **Request duration** | **30 seconds** max ([gateway limits](https://learn.microsoft.com/en-us/azure/api-management/api-management-gateways-overview)) | Fail for long RAG answers |
| **VNet / private OpenAI** | **No** VNet injection or outbound VNet integration on Consumption ([feature comparison](https://learn.microsoft.com/en-us/azure/api-management/api-management-features)) | Fail if OpenAI is private-only |

**Decision for AQREM v1:** Deploy **APIM Standard v2** (`StandardV2_1`) with **VNet integration** for outbound to Azure OpenAI (public or private endpoint). Enables **llm-token-limit**, streaming/SSE on v2 tiers, and longer requests. **Cost:** Standard v2 ≈ **$700/month per unit** (verify in [APIM pricing](https://azure.microsoft.com/pricing/details/api-management/) for your offer). **Alternative:** custom **model gateway** Container App (~$30–80/mo + engineering) if budget blocks APIM until revenue.

OpenAI path when APIM is public-only: AOAI account may use **public network + RBAC** for gateway MI; client Container Apps **never** get OpenAI RBAC.

## D5 — Models (default region: West Europe)

| Model | Version | Status (Learn retirement schedule) | Notes |
|-------|---------|--------------------------------------|-------|
| **gpt-4.1-mini** | 2025-04-14 | GA / newer chat default candidate | Replacement path from deprecated mini models |
| **gpt-4o-mini** | 2024-07-18 | **Deprecated**; deployment retirement **2027-10-01** | Avoid for new prod |
| **text-embedding-3-small** | 1 | GA; retirement **2028-02-09** (Learn schedule) | **1536** dimensions → `EMBEDDING_DIMENSIONS=1536` |

Platform Terraform defaults: **gpt-4.1-mini** chat + **text-embedding-3-small** v1. Confirm SKU availability in target region before apply ([region availability](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability)).

## D6 — PostgreSQL (West Europe list pricing)

| Option | Approximate compute (Oct 2026) | Notes |
|--------|--------------------------------|-------|
| **Dedicated B1ms** | **~$12.41/mo** compute (US list); **~$15/mo** WE indicative + **~$0.115/GiB** storage | Default **per client** all plans |
| **Shared server, DB-per-client** | One B1ms **~$15/mo** + storage shared | Saves **~$12–15/mo per client** only at scale; **not default** per your decision |

Example dedicated Starter: B1ms + 32 GiB ≈ **$16–20/mo** ([pricing structure](https://azure.microsoft.com/pricing/details/postgresql/flexible-server/)).

## D8 — Front Door Standard

| Check | Result |
|-------|--------|
| Private Link to origin | **Premium only** ([origin security](https://learn.microsoft.com/en-us/azure/frontdoor/origin-security)). Standard: **IP restriction + `X-Azure-FDID`** on Container Apps ingress. |
| Wildcard TLS | **Wildcard** `*.aqrem.app`: use **BYO cert in platform Key Vault** with Front Door managed identity, or **per-subdomain managed certs** (auto-rotate). Wildcard managed certs: **no auto-rotation** ([Domains](https://learn.microsoft.com/en-us/azure/frontdoor/domain)). |
| WAF on Standard | **Custom rules** tier ≈ **$35/mo** base profile component ([pricing comparison](https://learn.microsoft.com/en-us/azure/frontdoor/understanding-pricing)). |

## D13 — No Redis v1

Rate limits at **APIM** (or custom gateway); ingestion via **Storage Queue / Service Bus** only.
