# Container Apps cell model

## Definitions

- **Cell:** One VNet + one Container Apps **managed environment** + NAT Gateway (static egress) + subnet for apps and private endpoints.
- **Business client:** Dedicated cell (single tenant in that environment).
- **Starter/Standard clients:** Packed into shared cells; control plane assigns `cellId` at onboarding.

## Capacity formula

```
required_cores(client) ≈ api_min_replicas * api_cores + web_min_replicas * web_cores + worker_active_replicas * worker_cores
```

Use plan parameters from client-stack (Stage 2). Block onboarding when:

`cell.used_cores + required_cores > cell.core_quota - headroom`

Default **headroom:** 4 cores for platform burst.

## Control plane fields (platform DB)

- `cells(id, region, environment, core_quota, used_cores, vnet_id, cae_id, nat_egress_ip, status)`
- `organizations.cell_id` (nullable until assigned)
- `organizations.dedicated_environment` (bool, true for Business)

## Isolation checklist (Phase 4)

1. Client A MI cannot access client B storage/KV/PG (RBAC).
2. Client A cannot invoke client B internal FQDN without credentials (401/403).
3. Client A gateway subscription cannot meter against client B product.
