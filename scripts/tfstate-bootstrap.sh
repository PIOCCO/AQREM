#!/usr/bin/env bash
# Create the Terraform remote-state storage (infra/terraform/stacks/state). Run ONCE per platform by an
# operator with Owner (or Contributor + User Access Administrator) on the subscription.
#
#   scripts/tfstate-bootstrap.sh --validate-only        # no Azure calls: init -backend=false + validate
#   scripts/tfstate-bootstrap.sh                        # plan, confirm, apply (billable: one storage account)
#
# Needs infra/terraform/stacks/state/terraform.tfvars (copy terraform.tfvars.example; gitignored).
# After apply it prints how to move this stack's own state into tfstate-platform (it starts local).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/infra/terraform/stacks/state"
umask 077   # local state/plan files readable by the operator only

if [[ "${1:-}" == "--validate-only" ]]; then
  terraform init -backend=false -input=false >/dev/null
  terraform validate
  exit 0
fi
[[ -f terraform.tfvars ]] || { echo "Missing terraform.tfvars (copy terraform.tfvars.example)" >&2; exit 2; }

terraform init -input=false
terraform plan -input=false -out=state.tfplan
read -r -p "Apply (creates/changes the state storage account)? [y/N] " ok
[[ "$ok" == y || "$ok" == Y ]] || { rm -f state.tfplan; echo "Aborted."; exit 1; }
terraform apply -input=false state.tfplan
rm -f state.tfplan   # plan files can contain sensitive values

SA="$(terraform output -raw storage_account_name)"; RG="$(terraform output -raw resource_group_name)"
cat <<MSG

State storage ready: $SA (rg $RG). Next:
  1. Move THIS stack's state into it (then delete the local terraform.tfstate*):
       cat > backend.tf <<BE
terraform {
  backend "azurerm" {
    resource_group_name  = "$RG"
    storage_account_name = "$SA"
    container_name       = "tfstate-platform"
    key                  = "state/bootstrap.tfstate"
    use_azuread_auth     = true
  }
}
BE
       terraform init -migrate-state && shred -u terraform.tfstate terraform.tfstate.backup 2>/dev/null || true
  2. For new clients: export AQREM_TFSTATE_RG=$RG AQREM_TFSTATE_ACCOUNT=$SA, add the client id to
     'clients' here and re-apply BEFORE scripts/new-client-env.sh (its container must exist).
MSG
