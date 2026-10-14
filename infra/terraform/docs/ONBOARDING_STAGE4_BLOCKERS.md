# Onboard workflow — still requires Stage 4 app/product work

The GitHub `onboard-client` workflow implements Terraform plan/apply, internal gateway mint → Key Vault (no plaintext in logs), and HTTP `/ready` check. These **cannot be completed in IaC alone**:

| Step | Blocker |
|------|---------|
| Control-plane deployment row + resume | Product API writes `platform.client_deployments` |
| Tenant app migrations (beyond embedding metadata SQL) | App migration runner + schema in `backend/` |
| Storage / queue / DB deep health | Diagnostic endpoints on client API |
| Gateway call health | Client API configured with gateway key from KV |
| Register URL in control-plane | Product API or worker callback |
| Admin invitation link | Brevo + invitation token API (`PUBLIC_BASE_URL/accept-invite?token=`) |
| Mark ACTIVE / FAILED with resume | Worker callback + `resume_deployment_id` handler |

Stage 4 should implement the product API enqueue, worker callbacks, and health/diagnostic routes.
