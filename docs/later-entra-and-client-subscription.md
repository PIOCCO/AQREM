# Later (not built): Entra ID sign-in and deployment in the client's subscription

## Entra ID (Microsoft) sign-in
Config hook exists: `AUTH_PROVIDER=local` (only supported value). Needed:
* App registration per environment (dedicated) or a multi-tenant app (shared) with redirect URI
  `https://<env>/auth/callback`; settings `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, client secret or
  certificate in Key Vault (or federated credential from the managed identity).
* Backend: OIDC authorization-code + PKCE flow, validate ID token (issuer, audience, nonce, `tid`
  allow-list), map `oid` → `users` (new column `external_subject`, unique per issuer), then mint the
  existing AQREM JWT so the rest of the API is unchanged. Group/app-role claims → AQREM roles
  (Org admin/Editor/Reviewer/Viewer) with an admin-configurable mapping; just-in-time provisioning bound
  by license seats.
* Dedicated: first-admin setup could be replaced by "first Entra user in group X becomes Org admin".
* Disable local passwords per org when SSO is enforced; keep a break-glass local admin.
* Audit: log SSO sign-ins with `tid`/`oid`, never tokens.

## Running in the client's own subscription / network
* Terraform: the dedicated stack already takes everything as variables; add inputs for an existing
  VNet/subnets, existing private DNS zones (clients usually centralise them in a hub), existing Key Vault,
  and skip the NAT/public IP when egress goes through the client's firewall. Provider auth via a
  service principal/managed identity granted by the client (e.g. Azure Lighthouse delegation, or the
  client runs Terraform themselves from our released module).
* Images: publish to a registry the client can pull from (or they import into their ACR); pin by digest.
* Azure OpenAI: client-owned resource and deployments (`AZURE_OPENAI_ENDPOINT`, deployment names);
  private endpoint in their network; quota is theirs.
* License: unchanged (offline file); fleet view needs reachability to `/api/v1/version` and `/health`
  (outbound push of the same JSON to our endpoint is an alternative when inbound access is not allowed).
* Updates: client-run `rollout-dedicated.sh` or a pipeline they approve; support access only by
  just-in-time elevation they grant.
