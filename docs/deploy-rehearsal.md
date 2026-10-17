# Deployment rehearsal (dedicated tier) — Azure Cloud Shell

A first end-to-end run of one **fake dedicated client** (`rehtest`) in your subscription, then teardown.
Everything is run by you, manually, in Azure Cloud Shell (Bash). Nothing here has been run against Azure
by the repository automation; expect to fix things Azure rejects (note them, they are the point of the
rehearsal).

Inputs (from you): existing resource group `rg-aqrem-dev` in `swedencentral`, Azure OpenAI account
`aoai-aqrem-dev-sc01` with deployments `aqrem-chat` (gpt-5.4-mini) and `aqrem-embeddings` (1536 dims),
Terraform 1.11.4 in `~/bin`.

💰 = creates billable resources. Billing continues until step 7 (teardown).

| Step | Billable? |
|---|---|
| 0 Prepare | no |
| 1 State storage (`stacks/state`) | 💰 one storage account (cents/month) |
| 2 Registry + images | 💰 ACR Basic (daily charge) + ACR build minutes |
| 3 Dedicated client (`new-client-env.sh`) | 💰💰 PostgreSQL Flexible B2s, Container Apps (api, worker, beat, web, redis — min 1 replica each — plus the migrate job), NAT gateway + public IP, 3 private endpoints (Key Vault, Blob, Azure OpenAI), private DNS zones, Key Vault, storage |
| 4 License | no |
| 5 Setup token + admin | no |
| 6 Verification | 💰 Azure OpenAI tokens (chat + embeddings) |
| 7 Teardown | stops the costs (Key Vault stays soft-deleted, free) |

## 0. Prepare (Cloud Shell)
```bash
export PATH="$HOME/bin:$PATH"; terraform version            # expect v1.11.4
az account show --query '{sub:id, tenant:tenantId, user:user.name}' -o table
export SUB=$(az account show --query id -o tsv) TENANT=$(az account show --query tenantId -o tsv)
export ME=$(az ad signed-in-user show --query id -o tsv)      # your object id (an identifier, not a secret)
export LOC=swedencentral CLIENT=rehtest
export CS_IP=$(curl -s https://api.ipify.org); echo "Cloud Shell egress IP: $CS_IP"
# The branch must be pushed first (the CHECK commits are local until you push).
git clone https://github.com/PIOCCO/AQREM.git aqrem && cd aqrem && git checkout enterprise-tenancy
export TAG="rehearsal-$(git rev-parse --short HEAD)"
scripts/tfstate-bootstrap.sh --validate-only                   # offline checks, no Azure calls
scripts/new-client-env.sh "$CLIENT" "$LOC" small --validate-only
```
Cloud Shell's egress IP can change when the session restarts. If a later step fails with *403 Forbidden* on
Key Vault, refresh `CS_IP` and update `deployer_ip_cidrs` (step 3) before re-running.

## 1. State storage (💰) — `infra/terraform/stacks/state`
```bash
cd infra/terraform/stacks/state
cat > terraform.tfvars <<EOF2
subscription_id      = "$SUB"
tenant_id            = "$TENANT"
location             = "$LOC"
storage_account_name = "staqremtfstate$(openssl rand -hex 3)"   # globally unique, 3-24 lowercase
clients              = ["$CLIENT"]
platform_state_principal_ids = { me = "$ME" }
client_state_principal_ids   = { $CLIENT = { me = "$ME" } }
EOF2
cd ../../../..
scripts/tfstate-bootstrap.sh            # shows the plan, asks "Apply …? [y/N]"
```
Review the plan: 1 resource group `rg-aqrem-tfstate`, 1 storage account (ZRS, TLS1_2, shared key off),
containers `tfstate-platform` + `tfstate-rehtest`, 2 role assignments for you, 1 delete lock. Answer `y`.
Then follow the printed step 1 (write `backend.tf`, `terraform init -migrate-state`), **after waiting
~5 minutes** for the role assignment to propagate (otherwise the migrate fails with 403; just retry):
```bash
cd infra/terraform/stacks/state
# paste the backend.tf block printed by the script, then:
export ARM_USE_AZUREAD=true
terraform init -migrate-state          # answer "yes"; then remove the local copies:
shred -u terraform.tfstate terraform.tfstate.backup 2>/dev/null || true
export AQREM_TFSTATE_RG=$(terraform output -raw resource_group_name)
export AQREM_TFSTATE_ACCOUNT=$(terraform output -raw storage_account_name)
cd ../../../..
```

## 2. Registry and images (💰)
The dedicated stack pulls `aqrem-api`, `aqrem-worker`, `aqrem-web` (tag = `image_tag`) and
`redis:7-alpine` from your ACR (`infra/terraform/modules/dedicated_env/apps.tf`).
```bash
export ACR=acraqremdev$(openssl rand -hex 3)
az acr create -g rg-aqrem-dev -n "$ACR" --sku Basic -l "$LOC" -o none
export ACR_SERVER=$(az acr show -n "$ACR" --query loginServer -o tsv) ACR_ID=$(az acr show -n "$ACR" --query id -o tsv)
az acr build -r "$ACR" -t "aqrem-api:$TAG"    -f infra/docker/Dockerfile.api .
az acr build -r "$ACR" -t "aqrem-worker:$TAG" -f infra/docker/Dockerfile.worker .
az acr build -r "$ACR" -t "aqrem-web:$TAG"    -f infra/docker/Dockerfile.web --build-arg VITE_BUILD_ID="$TAG" .
az acr import -n "$ACR" --source docker.io/library/redis:7-alpine --image redis:7-alpine
az acr repository list -n "$ACR" -o table          # expect aqrem-api, aqrem-worker, aqrem-web, redis
```

## 3. Deploy the fake client (💰💰) — `scripts/new-client-env.sh`
Platform values (shared by all clients; file is gitignored):
```bash
AOAI_ID=$(az cognitiveservices account show -g rg-aqrem-dev -n aoai-aqrem-dev-sc01 --query id -o tsv)
AOAI_EP=$(az cognitiveservices account show -g rg-aqrem-dev -n aoai-aqrem-dev-sc01 --query properties.endpoint -o tsv)
cat > infra/terraform/stacks/dedicated/platform.auto.tfvars <<EOF2
tenant_id                   = "$TENANT"
subscription_id             = "$SUB"
registry_login_server       = "$ACR_SERVER"
acr_id                      = "$ACR_ID"
image_tag                   = "$TAG"
openai_account_id           = "$AOAI_ID"
openai_endpoint             = "$AOAI_EP"
openai_chat_deployment      = "aqrem-chat"
openai_embedding_deployment = "aqrem-embeddings"
deployer_ip_cidrs           = ["$CS_IP/32"]
EOF2
```
Rehearsal-only client values (extra `*.auto.tfvars` in the client workspace; the script only rewrites
`client.auto.tfvars`). `LAPTOP_IP` = public IP of the browser machine you will use for `/setup`
(run `curl -s https://api.ipify.org` **on that machine**):
```bash
export LAPTOP_IP=<your laptop public IP>
mkdir -p infra/terraform/clients/$CLIENT
cat > infra/terraform/clients/$CLIENT/rehearsal.auto.tfvars <<EOF2
organization_name       = "Rehearsal Test Org"
setup_allowed_cidrs     = ["$LAPTOP_IP/32"]
setup_token_ttl_minutes = 240
EOF2
```
Plan, review, apply:
```bash
scripts/new-client-env.sh "$CLIENT" "$LOC" small --plan-only    # review the plan output
rm -f infra/terraform/clients/$CLIENT/tfplan                     # plan file: delete after review
scripts/new-client-env.sh "$CLIENT" "$LOC" small                 # re-plans, asks "Apply …? [y/N]"
```
Review checklist for the plan: everything in `rg-aqrem-rehtest` except a private endpoint connection +
role assignment on `aoai-aqrem-dev-sc01` and an `AcrPull` assignment on the ACR; no `destroy`/`replace` of
anything in `rg-aqrem-dev`; Key Vault secrets show `(write-only attribute)`, no secret values.
The script then starts the migrate job and prints the URL and the setup-token command.
```bash
cd infra/terraform/clients/$CLIENT; export ARM_USE_AZUREAD=true
export RG=$(terraform output -raw resource_group_name) KV=$(terraform output -raw key_vault_name)
export URL=$(terraform output -raw public_url) FQDN=${URL#https://}
JOB=$(terraform output -raw migration_job_name); cd -
az containerapp job execution list -n "$JOB" -g "$RG" -o table     # wait for Succeeded
# The api may have started before the schema existed; restart it once after the job succeeded:
az containerapp revision restart -n $CLIENT-api -g "$RG" \
  --revision "$(az containerapp show -n $CLIENT-api -g "$RG" --query properties.latestRevisionName -o tsv)"
```
If apply fails with Key Vault 403 right after creating the vault: RBAC propagation; wait 5 minutes and run the
same command again (Terraform continues where it stopped).

## 4. Issue a test license (no cost)
The rehearsal uses the **development** signing key (the image only trusts it; see `docs/licensing.md`).
Sign on the machine that holds it (the agent box keeps it in `~/.aqrem-license-keys/`; never copy the
private key into Cloud Shell or the repo):
```bash
python3 scripts/aqrem_license.py sign --key ~/.aqrem-license-keys/aqrem-license-private.pem \
  --org "Rehearsal Test Org" --slug rehtest --environment rehtest --seats 5 --expires 2027-01-31 \
  --out rehtest.license.json
python3 scripts/aqrem_license.py verify --license rehtest.license.json --slug rehtest --environment rehtest
```
Variants for step 6 (same command, change only): `--expires <date within 30 days>` (warning) and
`--environment other` (mismatch). Upload the JSON files to Cloud Shell (Upload button); the license is
signed, not secret. **Do not install it yet** (step 6 checks the unlicensed state first).

## 5. Setup token and first admin (no cost)
Run the X-Forwarded-For test **before** creating the admin (afterwards `/setup` is 404 for everyone):
follow `docs/operations-dedicated.md` → "Real-deployment test procedure" with *allowed* = your laptop and
*other* = Cloud Shell. Short version:
```bash
# laptop:      curl -s -o /dev/null -w '%{http_code}\n' https://$FQDN/api/v1/setup/status        -> 200
# laptop:      curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Forwarded-For: 10.0.0.1' https://$FQDN/api/v1/setup/status -> 200
# Cloud Shell:
curl -s -o /dev/null -w '%{http_code}\n' https://$FQDN/api/v1/setup/status                       # 404
curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Forwarded-For: '"$LAPTOP_IP" https://$FQDN/api/v1/setup/status  # 404 (spoof)
az containerapp logs show -n $CLIENT-api -g "$RG" --tail 200 | grep 'setup gate:'
# expect client_ip=<LAPTOP_IP> via=forwarded allowed=True and client_ip=<CS_IP> ... allowed=False
```
Then the token (prints on your terminal only; don't paste it into chats or tickets):
```bash
az keyvault secret show --vault-name "$KV" -n setup-token --query value -o tsv
```
On the laptop open `https://$FQDN/setup`, enter the token, admin e-mail, name, password (≥ 12 chars).
Afterwards: `curl -s -o /dev/null -w '%{http_code}\n' https://$FQDN/api/v1/setup/status` → `404` from both
machines. Close the network window: delete `setup_allowed_cidrs` from `rehearsal.auto.tfvars` and re-run
`scripts/new-client-env.sh "$CLIENT" "$LOC" small`.

## 6. Verification checklist
- [ ] **Health**: `curl -s https://$FQDN/health | python3 -m json.tool` — database (schema 7), broker, storage,
      llm OK; `curl -s https://$FQDN/api/v1/version` reports `$TAG`, `deployment_mode: dedicated`.
- [ ] **Login**: `https://$FQDN/login` with the admin; org admin console at `/org-admin`.
- [ ] **Unlicensed = read-only** (no license installed yet): red "Read-only mode" banner; uploading a document in
      `/org-admin/documents` is refused ("read-only mode"); browsing works.
- [ ] **Install the license**: `az keyvault secret set --vault-name "$KV" -n license-key --file rehtest.license.json -o none`,
      restart the api revision (command in step 3). Banner disappears; `/health` → `license.status: valid`.
- [ ] **Upload PDF**: `/org-admin/documents` → upload a small PDF → status becomes indexed (worker logs:
      `az containerapp logs show -n $CLIENT-worker -g "$RG" --tail 100`).
- [ ] **Chat answer with sources**: ask a question answered by the PDF at `/`; the answer cites the document.
      Ask something unrelated: the assistant says it found nothing (grounded-only).
- [ ] **Isolation**: platform console is closed in dedicated mode:
      `curl -s -o /dev/null -w '%{http_code}\n' https://$FQDN/api/v1/admin/organizations` → `404`;
      `/org-admin` shows only "Rehearsal Test Org" (a dedicated environment has its own database; cross-
      organization isolation inside one database is covered by the local isolation matrix tests). Optional in-org check: invite a
      second user, restrict the PDF to a group without them (`/org-admin/access`), their chat finds nothing.
- [ ] **License states**: install the "expires within 30 days" file → amber "License notice" for admins only;
      install the `--environment other` file → amber grace banner ("issued for a different organization or
      environment … until DATE"); reinstall the valid file → no banner. (Restart the api revision after each
      `secret set`.) Read-only after grace can't be shown without waiting 14 days; it is covered by tests.
- [ ] **Setup not internet-reachable**: from Cloud Shell `.../api/v1/setup/status` → `404` (already checked in step 5).
- [ ] **X-Forwarded-For**: done in step 5; record the `setup gate:` log lines in your notes.
- [ ] Record every deviation (Azure errors, manual fixes) for the follow-up.

## 7. Teardown (stops the costs)
```bash
cd infra/terraform/clients/$CLIENT && export ARM_USE_AZUREAD=true
terraform destroy          # review: only rg-aqrem-rehtest resources + the PE/role assignments on AOAI/ACR; answer "yes"
cd -
az acr delete -n "$ACR" -y                                   # or keep the registry for the next rehearsal
az group show -n rg-aqrem-rehtest -o none 2>/dev/null && echo "RG still exists - check the portal"
```
* Key Vault becomes soft-deleted (purge protection, 90 days, no cost; the random suffix avoids name clashes).
* PostgreSQL backups are deleted with the server.
* The state storage account is protected (`CanNotDelete` lock + `prevent_destroy`). Keeping it costs cents.
  To remove it as well: `az lock delete -g rg-aqrem-tfstate -n <lock name from 'az lock list -g rg-aqrem-tfstate'>`
  then `az group delete -n rg-aqrem-tfstate`.
* If destroy fails with Key Vault 403, your Cloud Shell IP changed: update `deployer_ip_cidrs` and retry.
* Delete local leftovers: `rm -rf infra/terraform/clients/$CLIENT *.license.json`.
