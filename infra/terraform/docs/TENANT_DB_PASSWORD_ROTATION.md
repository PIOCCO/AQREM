# Tenant PostgreSQL password rotation (write-only path)

## Prerequisites

- Terraform **≥ 1.11**, ephemeral `random_password`, `administrator_password_wo`, Key Vault `value_wo`
- Increment **`administrator_password_wo_version`** and **`value_wo_version`** together on each rotation

## Steps

1. Generate a new ephemeral password in Terraform (new apply plan shows version bump only — no cleartext in plan/state).
2. In `modules/client_stack/main.tf` (or tfvars-driven locals), increment both version fields, e.g. `2`:

```hcl
administrator_password_wo_version = 2
value_wo_version                  = 2
```

3. `terraform plan` — confirm no password strings in plan output.
4. `terraform apply` (with explicit approval) — Azure PG admin password and Key Vault secret update atomically per provider semantics.
5. Rolling restart client **api** and **worker** Container Apps so apps reload the secret from Key Vault / env.
6. Verify connectivity; revoke old DB sessions if needed (`pg_stat_activity`).
7. Run `infra/terraform/tests/verify_password_not_in_state.sh terraform.tfstate`.

## Verify rotation worked

- Connect with new password from Key Vault (never from Terraform state).
- Old password must fail authentication.

## Fallback (non write-only)

See earlier sections: encrypted remote state + manual `az postgres flexible-server update` + KV update.
