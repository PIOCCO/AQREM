# Only the human can do this

Commands assume repo root and an Azure dev subscription.

1. **Terraform apply (platform + client)** — requires your approval and `az login`:
   ```bash
   cd infra/terraform/stacks/platform && terraform init && terraform plan
   cd infra/terraform/stacks/client && terraform init && terraform plan -var-file=../../parameters/clients/acme.sample.tfvars.json
   ```

2. **Mint live gateway keys** — onboard workflow or Entra-protected internal mint API; store in client Key Vault (never commit).

3. **Configure real Azure OpenAI** — deployments behind the model gateway (not in app containers).

4. **Brevo + DNS** — `EMAIL_PROVIDER=brevo`, SPF/DKIM (`infra/terraform/docs/EMAIL_DNS.md`).

5. **Production URLs** — set `PUBLIC_BASE_URL`, `VITE_PUBLIC_APP_URL`, `CORS_ALLOWED_ORIGINS` to your real domain.

6. **k6 load test** — `infra/terraform/docs/GATEWAY_LOAD_TEST.md` against deployed gateway URL.

7. **Backup/restore drill** — Azure PG + blob retention per your policy (scripts under `scripts/ops/` when added for Azure).

8. **Sign-off** — update `docs/RELEASE_READINESS.md` dated RAN table after your staging smoke.
