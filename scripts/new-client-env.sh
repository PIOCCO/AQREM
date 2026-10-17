#!/usr/bin/env bash
# Create (or update) a dedicated AQREM environment for one client.
#
#   scripts/new-client-env.sh <client> <region> <size> [--existing-db] [--plan-only] [--yes]
#
#   client   lowercase id, e.g. contoso
#   region   Azure region, e.g. westeurope
#   size     small | medium | large
#   --existing-db  use an existing PostgreSQL: export AQREM_EXISTING_DATABASE_URL (app role) and optionally
#                  AQREM_EXISTING_MIGRATION_DATABASE_URL (owner role) before running. Values go write-only
#                  into Key Vault (never into Terraform state).
#   --plan-only    stop after `terraform plan`.
#   --yes          skip the interactive confirmation before apply.
#   --validate-only  init -backend=false + validate the generated workspace (no Azure calls).
#   --allow-local-state  explicitly allow local state (sandbox only; state holds infrastructure details).
#
# Remote state (required by default): AQREM_TFSTATE_RG + AQREM_TFSTATE_ACCOUNT (created by
#   scripts/tfstate-bootstrap.sh). Each client has its OWN container tfstate-<client> (RBAC per container,
#   Entra ID auth, no storage keys) and key dedicated/<client>.tfstate.
#
# Prerequisites: az login (subscription selected), terraform >= 1.11,
#   infra/terraform/stacks/dedicated/platform.auto.tfvars (copy platform.auto.tfvars.example),
#   AQREM_TFSTATE_RG / AQREM_TFSTATE_ACCOUNT (remote state, see above).
set -euo pipefail

usage() { sed -n '2,20p' "$0"; exit 1; }
[[ $# -ge 3 ]] || usage
CLIENT="$1"; REGION="$2"; SIZE="$3"; shift 3
DB_MODE=new; PLAN_ONLY=0; YES=0; VALIDATE_ONLY=0; ALLOW_LOCAL=0
for a in "$@"; do
  case "$a" in
    --existing-db) DB_MODE=existing ;;
    --plan-only) PLAN_ONLY=1 ;;
    --yes) YES=1 ;;
    --validate-only) VALIDATE_ONLY=1 ;;
    --allow-local-state) ALLOW_LOCAL=1 ;;
    *) usage ;;
  esac
done
[[ "$CLIENT" =~ ^[a-z][a-z0-9-]{2,19}$ ]] || { echo "client must match ^[a-z][a-z0-9-]{2,19}$" >&2; exit 2; }
[[ "$SIZE" =~ ^(small|medium|large)$ ]] || { echo "size must be small|medium|large" >&2; exit 2; }

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STACK="$ROOT/infra/terraform/stacks/dedicated"
WORK="$ROOT/infra/terraform/clients/$CLIENT"
mkdir -p "$WORK"
[[ -f "$STACK/platform.auto.tfvars" || $VALIDATE_ONLY == 1 ]] || { echo "Missing $STACK/platform.auto.tfvars (copy the .example)" >&2; exit 2; }

# Per-client workspace: symlink the stack so every client has its own .terraform + state.
for f in "$STACK"/*.tf "$STACK"/platform.auto.tfvars; do [[ -e "$f" ]] && ln -sf "$f" "$WORK/"; done
cat > "$WORK/client.auto.tfvars" <<VARS
client   = "$CLIENT"
location = "$REGION"
size     = "$SIZE"
db_mode  = "$DB_MODE"
existing_has_migration_url = $([[ -n "${AQREM_EXISTING_MIGRATION_DATABASE_URL:-}" ]] && echo true || echo false)
VARS

if [[ "$DB_MODE" == existing ]]; then
  [[ -n "${AQREM_EXISTING_DATABASE_URL:-}" ]] || { echo "--existing-db needs AQREM_EXISTING_DATABASE_URL" >&2; exit 2; }
  export TF_VAR_existing_database_url="$AQREM_EXISTING_DATABASE_URL"
  [[ -n "${AQREM_EXISTING_MIGRATION_DATABASE_URL:-}" ]] && export TF_VAR_existing_migration_database_url="$AQREM_EXISTING_MIGRATION_DATABASE_URL"
fi

cd "$WORK"
if [[ $VALIDATE_ONLY == 1 ]]; then
  terraform init -backend=false -input=false >/dev/null
  terraform validate
  exit 0
fi
umask 077  # plan/local state files: operator-only
if [[ -n "${AQREM_TFSTATE_RG:-}" && -n "${AQREM_TFSTATE_ACCOUNT:-}" ]]; then
  # Separate state per client: own container (RBAC boundary) + own key. Entra ID auth only.
  cat > backend.tf <<BE
terraform {
  backend "azurerm" {
    resource_group_name  = "$AQREM_TFSTATE_RG"
    storage_account_name = "$AQREM_TFSTATE_ACCOUNT"
    container_name       = "tfstate-$CLIENT"
    key                  = "dedicated/$CLIENT.tfstate"
    use_azuread_auth     = true
  }
}
BE
  export ARM_USE_AZUREAD=true
elif [[ $ALLOW_LOCAL == 1 ]]; then
  rm -f backend.tf
  echo "WARNING: --allow-local-state: state stays in $WORK/terraform.tfstate (gitignored). Sandbox only." >&2
else
  echo "Remote state required: export AQREM_TFSTATE_RG and AQREM_TFSTATE_ACCOUNT (scripts/tfstate-bootstrap.sh)," >&2
  echo "and add '$CLIENT' to 'clients' in stacks/state so container tfstate-$CLIENT exists. Or pass --allow-local-state." >&2
  exit 2
fi

terraform init -input=false
# Plan files can contain sensitive values (Terraform masks them on screen, not in the file):
# keep it 0600 in the gitignored client dir and delete it after apply/abort.
terraform plan -input=false -out=tfplan
[[ $PLAN_ONLY == 1 ]] && { echo "Plan saved to $WORK/tfplan (not applied; contains infrastructure details — delete it when done)."; exit 0; }
if [[ $YES != 1 ]]; then
  read -r -p "Apply this plan for client '$CLIENT' (creates billable Azure resources)? [y/N] " ok
  [[ "$ok" == y || "$ok" == Y ]] || { rm -f tfplan; echo "Aborted."; exit 1; }
fi
terraform apply -input=false tfplan
rm -f tfplan

RG="$(terraform output -raw resource_group_name)"
JOB="$(terraform output -raw migration_job_name)"
echo "Running database migrations ($JOB)…"
az containerapp job start -n "$JOB" -g "$RG" -o none
echo
echo "Done. URL: $(terraform output -raw public_url)"
echo "Setup token (give to the client admin once):"
echo "  az keyvault secret show --vault-name $(terraform output -raw key_vault_name) -n setup-token --query value -o tsv"
echo "  It works ONCE and expires SETUP_TOKEN_TTL_MINUTES (default 60) after the first api start."
echo "  /setup only answers clients inside setup_allowed_cidrs (default: private networks only)."
echo "  Deliver URL and token over SEPARATE channels (docs/operations-dedicated.md, 'Delivering the setup token')."
echo "  Expired/lost before the first admin: az containerapp exec -n <client>-api -g <rg> --command 'python -m app.setup reset --confirm'"
echo "Install the client's license: store it as Key Vault secret 'license-key', then restart the api revision."
