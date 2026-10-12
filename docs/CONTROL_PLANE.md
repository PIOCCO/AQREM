# Control plane vs data plane

## Deployment model (this repository)

AQREM V1 runs as a **shared multi-tenant** FastAPI application with **organization-scoped** data in PostgreSQL. Customer isolation is enforced by `organization_id` on every data-plane query, not separate physical environments per client unless a provisioning adapter creates them.

## Surfaces

| Surface | Route | Identity |
|---------|-------|----------|
| Employee workspace | `/chat` (also `/`) | Organization member |
| Client admin | `/admin` | `ORG_ADMIN` (org-admin APIs) |
| Master console | `/master-admin` | Platform administrator |

Legacy `/platform-admin` redirects to `/master-admin`.

## Control plane (master)

- Metadata: organizations, licenses, environments, provisioning jobs, allowlisted telemetry.
- **No** ordinary endpoints for evidence content, chat transcripts, embeddings, or secrets.

## Data plane (tenant)

- Documents, evidence, RAG, questionnaires — require `X-Organization-Id` and membership.
- Client admins configure sources and AI within their tenant via existing AQREM APIs.

## Provisioning

- Jobs are recorded in `provisioning_jobs`.
- **Local/dev adapter** sets logical URLs only (`/chat`, `/admin`).
- **Production** without Azure adapter configuration → job status `blocked`, not success.

## Telemetry allowlist

See `app/services/telemetry.py`. Events must not include document text, questions, answers, or secrets.

## Break-glass

Customer-approved support access to content is **not implemented** in V1; do not bypass tenant isolation via the master console.
