# Provisioner identity guardrails (D10)

## Custom role wired in platform stack

Module: `infra/terraform/modules/provisioning_role`

### Allowed actions (summary)

| Action group | Purpose |
|--------------|---------|
| `Microsoft.Resources/subscriptions/resourceGroups/*` | Create/delete RGs under `aqrem-*` prefix (policy-enforced) |
| `Microsoft.Resources/deployments/*` | Terraform ARM deployments |
| `Microsoft.Authorization/roleAssignments/write/delete` | Assign **least-privilege** roles created by client stack (not Owner/UAA) |
| `Microsoft.ManagedIdentity/userAssignedIdentities/*` | Client MI |
| `Microsoft.KeyVault/vaults/*`, `Microsoft.Storage/storageAccounts/*` | Client secrets/storage |
| `Microsoft.DBforPostgreSQL/flexibleServers/*` | Tenant DB |
| `Microsoft.App/containerApps/*`, `managedEnvironments/read` | Client apps |
| `Microsoft.Network/virtualNetworks/subnets/join/action` | CAE/PG subnet join |
| `Microsoft.Cdn/profiles/*` | Front Door routes |

### Explicitly **not** granted

- `Owner`, `User Access Administrator`, or `Role Based Access Control Administrator` role definitions (never included in `actions`)
- `Microsoft.Authorization/roleDefinitions/write` (cannot mint new roles)
- `Microsoft.Authorization/elevateAccess/Action`

### Azure Policy (`platform_guardrail` module)

Denies resource **names** outside `${resource_prefix}*` and **locations** outside allow-list.

## What-if tests (run in dev subscription)

| Scenario | Expected |
|----------|----------|
| Create RG `contoso-rg` | **Denied** by policy |
| Create RG `aqrem-dev-acme` in `westeurope` | **Allowed** |
| `az role assignment create --role Owner` as provisioner SP | **AuthorizationFailed** (SP lacks permission to assign Owner) |
| `az role assignment create --role "User Access Administrator"` | **AuthorizationFailed** |
| Delete/update RG `aqrem-dev-otherclient` when logged in as provisioner | **Allowed only** if SP has scope on that RG; client stacks use **separate state per client** — pipeline inputs must match allow-list |

Automated unit test: `infra/terraform/tests/provisioner_role_test.go` N/A — see `tests/provisioner_role_actions_test.py` (static allow/deny list).
