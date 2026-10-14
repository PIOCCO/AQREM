# Tenant PostgreSQL password rotation (fallback path)

**Preferred:** Terraform **write-only** `administrator_password_wo` with **ephemeral** `random_password` (client stack) — password never in state.

If you cannot use TF ≥1.10 / azurerm ≥4.21:

1. Confirm remote state: **encrypted**, **private**, **RBAC-restricted**, **versioned**.
2. Rotate:
   - `az postgres flexible-server update --admin-password <new>` (or TF taint + apply with new random)
   - Update Key Vault secret `tenant-postgresql-password`
   - Rolling restart client API/worker Container Apps
3. Revoke old sessions / monitor failed auth metrics.
4. Record action in platform `audit_log`.
