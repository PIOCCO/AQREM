# Tenant PostgreSQL password — not in Terraform state

## Supported stack (pinned)

| Component | Version |
|-----------|---------|
| Terraform | **≥ 1.11.0** (write-only arguments) |
| azurerm | **~> 4.0** (4.21+, we use 4.81) |
| random | **~> 3.7** (`ephemeral "random_password"`) |

## Configuration (`modules/client_stack`)

```hcl
ephemeral "random_password" "tenant_db" { ... }

azurerm_postgresql_flexible_server.tenant {
  administrator_password_wo         = ephemeral.random_password.tenant_db[0].result
  administrator_password_wo_version = 1
}

azurerm_key_vault_secret.tenant_db_password {
  value_wo         = ephemeral.random_password.tenant_db[0].result
  value_wo_version = 1
}
```

Ephemeral + write-only values are **omitted from plan and state** (HashiCorp Terraform 1.11+).

## Proof procedure (run in dev/test after apply)

```bash
terraform apply -var-file=...   # only with explicit approval
./infra/terraform/tests/verify_password_not_in_state.sh terraform.tfstate
rg -F "$KNOWN_PASSWORD" terraform.tfstate && echo FAIL || echo OK
```

Agent verification (no apply): `terraform validate` on client stack with ephemeral + `value_wo` / `administrator_password_wo` passes.

## Fallback

If Terraform < 1.11: use encrypted private versioned remote state + `TENANT_DB_PASSWORD_ROTATION.md`.
