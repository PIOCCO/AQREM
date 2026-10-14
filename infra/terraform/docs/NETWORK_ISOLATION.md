# Network isolation within a cell (known limitation)

## What NSGs and private endpoints do **not** provide

Inside a **shared cell** (one VNet, shared subnets for Container Apps and private endpoints):

- **NSGs** filter traffic at subnet/NIC boundaries. They **cannot** restrict Container App A from talking to Container App B when both use the **same subnet**.
- **Private endpoints** for PostgreSQL, Storage, and Key Vault are reachable from **any workload in the cell VNet** that has routing and DNS resolution — not only the intended client.

Therefore: **a compromised container for client A may have network reachability to client B’s PostgreSQL private endpoint, storage account, or Key Vault endpoint.**

We do **not** claim L3 isolation between clients in the same cell.

## Isolation model (what we rely on today)

| Layer | Mechanism |
|-------|-----------|
| Database | **Dedicated PostgreSQL server** per client (default); unique login + password in **client Key Vault only** |
| Storage / queue | **Dedicated storage account**; MI + connection strings scoped to that account |
| Secrets | **Dedicated Key Vault** per client; RBAC to client MI only |
| Platform | **No shared tenant DB credentials** across clients; gateway keys are per-client hashes in control-plane DB |

**No shared credentials** anywhere in the cell.

## Hardening options (cost / ops tradeoffs)

| Option | Isolation gain | Cost / complexity |
|--------|----------------|-------------------|
| **(a) PostgreSQL Entra auth per client MI** | Removes long-lived DB password; authZ via AAD + PG roles | Medium — configure AAD auth on flexible server, per-client role |
| **(b) PG firewall / `pg_hba` where supported** | Restrict source IPs to client CA egress | Low–medium; must track per-client egress / subnet |
| **(c) Smaller cells** | Blast radius ↓ (fewer clients per VNet) | More CAEs, more ops overhead |
| **(d) Dedicated environment** (Business tier) | Strongest separation — own VNet/cell | Highest cost; required for sensitive clients |

## Phase 4 verification (required)

Automated tests must prove a **client A container** cannot authenticate to **client B**:

- PostgreSQL (wrong login/password and wrong Entra identity)
- Storage (wrong account key / MI)
- Key Vault (wrong vault RBAC)

Document results in the Phase 4 test report.
