# AQREM security overview (for clients)

This describes what is implemented in the code and infrastructure definitions today. Items marked
*planned* are not implemented.

## Deployment models
* **Shared**: one AQREM environment serves several organizations. Isolation is enforced by the
  application: every tenant record carries an `organization_id`; every query, vector search, file path
  and admin API is scoped to the signed-in user's organization (membership is verified on every request,
  a client-supplied organization header that does not match a membership is rejected). Automated tests
  with two organizations check that one cannot retrieve the other's chunks, documents, chats or admin
  data (`tests/backend/test_cross_org_isolation.py`).
  In addition, PostgreSQL **row-level security** is enabled and forced on every table holding client data
  (migration 3, `backend/app/db/rls.py`). Each database transaction of a tenant session runs with
  `SET LOCAL app.current_org` (set automatically for API requests and every background task); policies
  allow only rows of that organization and reject writes for another one. When no organization is set the
  database returns no tenant rows (fail closed). The runtime role is not a superuser, has no BYPASSRLS and
  owns no tables. Cross-organization access exists only for: (a) the control-plane group on identity/
  control tables (users, organizations, memberships, invitations), needed for sign-in by email, invitations,
  organization creation and the AQREM super-admin console - it does **not** extend to documents, chunks,
  sources, answers or audit data; (b) the migration role and a separately named, normally disabled
  `aqrem_support` role. Tests connect directly as a non-superuser role and prove SELECT/UPDATE/DELETE/INSERT
  and vector search cannot cross organizations (`tests/backend/test_rls_isolation.py`). RLS protects the
  database only when the deployment uses the least-privilege roles from `docs/sql/app_role.sql`; a
  superuser connection (e.g. the local Docker Compose default) bypasses it.
* **Dedicated**: one organization per environment with its own containers, its own PostgreSQL database,
  storage account and Key Vault, hosted in the AQREM Azure subscription. The multi-tenant platform console
  is disabled. Running inside the client's own subscription/network is *planned* (see below).

## Data flow and residency
* Documents are stored in Azure Blob Storage (or a local volume on self-hosted lab installs) under a
  per-organization prefix. Text chunks and embeddings are stored in PostgreSQL (pgvector).
* Questions and retrieved passages are sent to the configured Azure OpenAI deployment to generate
  answers and embeddings. The region is the one chosen for the environment and the Azure OpenAI resource.
  Microsoft's Azure OpenAI data-handling terms apply.
* Chats are kept in the user's browser; the server stores only conversations a user explicitly shares
  (snapshots that expire).
* No telemetry is sent to third parties; the web UI loads no external fonts or CDNs. Outbound calls
  go only to configured endpoints (database, storage, Key Vault, Azure OpenAI, optionally Document
  Intelligence, GitHub for GitHub sources, Brevo for e-mail if enabled).

## Encryption
* **In transit**: browser → web via HTTPS (Azure Container Apps ingress). Dedicated stack: PostgreSQL
  requires TLS (`require_secure_transport=on`, app connects with `sslmode=require`, startup check fails
  if TLS is missing in production); Key Vault, Blob and Azure OpenAI over HTTPS through private endpoints.
  Traffic between containers inside the environment's private network (web → api, api → redis) is plain
  HTTP/Redis inside the VNet.
* **At rest**: Azure Storage, Azure Database for PostgreSQL and Key Vault encrypt data at rest with
  Microsoft-managed keys. Customer-managed keys are *not configured* (*planned* option).
  Self-hosted lab installs (Docker Compose) rely on the host's disk encryption.
* Passwords are hashed with bcrypt; sessions are signed JWTs with separate audiences for employees,
  organization admins and platform staff.

## Secrets
* Dedicated/production: secrets (database URLs, signing key, setup token, license) live in Azure Key
  Vault and are read at startup with a managed identity; Terraform writes them write-only (not stored in
  Terraform state). Storage and Azure OpenAI are accessed with the managed identity (no keys).
* Logs pass through a redaction filter (connection-string credentials, storage keys/SAS, bearer tokens,
  JWTs, key/password values) and never include document text or chat content; production disables RAG
  debug logging. Diagnostics bundles contain only versions, dependency status and error summaries.

## Roles and access
* Organization roles: Org admin, Editor, Reviewer, Viewer. Org admins manage users, documents and settings.
* Platform roles (shared tier operators): Super admin, Support, Billing — with metadata-only console
  endpoints (no document content endpoints). In dedicated mode the platform console is off, or read-only
  for support when the client agrees (`DEDICATED_SUPPORT_ACCESS=true`).
* Database: separate least-privilege application role (DML only) and migration role (DDL) are supported
  and created automatically for new dedicated databases; the **Test database** check flags an app role
  that can run DDL.
* Licensing in dedicated mode: offline Ed25519-signed license file verified locally (seats, expiry, features).

## Audit logs
Security-relevant actions (invitations and joins, membership/role changes, password-reset requests, admin console entry, document
upload/delete and visibility changes, chat-share create/view/revoke, settings changes, first-admin setup) are written to an audit log per organization, viewable
and exportable by org admins. Optional retention (`AUDIT_RETENTION_DAYS`). Successful and failed sign-ins are not yet audited (*planned*).

## Network (dedicated)
VNet-integrated Container Apps; Key Vault, Storage, Azure OpenAI and Document Intelligence via private
endpoints with private DNS; PostgreSQL VNet-injected without public access; Storage public access and
shared keys disabled; Key Vault firewall default-deny (operator IPs only). Egress through a NAT gateway
with a fixed IP. Only the web app has public ingress.

## Not yet implemented (planned)
* Microsoft Entra ID single sign-on (see `docs/later-entra-and-client-subscription.md`).
* Deployment into the client's own Azure subscription / network.
* Customer-managed encryption keys, PostgreSQL row-level security for the shared tier, WAF/Front Door
  in front of dedicated environments, malware scanning service integration beyond the existing upload checks.
