# AQREM Version 1 — product scope

## Roles

| Role | V1 experience |
|------|----------------|
| **Super admin** | Unchanged (`/super-admin`) — org provisioning |
| **Org admin** | `/org-admin/documents` + `/org-admin/users` (+ back to chat) |
| **Employee** | Chat only (`/`, `/c/:id`) |

## Keep (V1)

- Login, invites, join, password flows
- Employee chat (new chat, search, history, composer, citations, feedback, regenerate)
- Org admin: company document upload/indexing, member invites
- Super-admin console
- Org-wide RAG (no project selected); `project_id` omitted in chat API

## Hidden (not deleted)

- Projects, Sources, Evidence browser, Questionnaires, Review Queue, Answer Library, Activity/Audit (employee), Settings (employee), Dashboard
- Chat scope picker, composer file attach (employee), answer action chips (upload/switch project/review queue)
- Org-admin: Overview wizard emphasis, Usage, Access, Data storage, Audit, Privacy (routes still exist if URL typed; nav removed)

Toggle full UI: `VITE_PRODUCT_V1=false` at build time.
