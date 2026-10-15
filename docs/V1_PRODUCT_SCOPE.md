# AQREM Version 1 — product scope

## Roles

| Role | V1 experience |
|------|----------------|
| **Super admin** | Unchanged (`/super-admin`) — org provisioning |
| **Org admin** | Full admin console (Overview/setup checklist, Documents, Members, Usage, Access, **Data storage**, Audit, Privacy) |
| **Employee** | Chat only (`/`, `/c/:id`) |

## Keep (V1)

- Login, invites, join, password flows
- Employee chat (new chat, search, history, composer, citations, feedback, regenerate)
- Org admin: company document upload/indexing (always **all staff** visibility — no upload picker), member invites, PostgreSQL onboarding via Data storage
- Super-admin console
- Org-wide RAG (no project selected); `project_id` omitted in chat API

## Hidden (not deleted)

- Projects, Sources, Evidence browser, Questionnaires, Review Queue, Answer Library, Activity/Audit (employee), Settings (employee), Dashboard
- Chat scope picker, composer file attach (employee), answer action chips (upload/switch project/review queue)
- Employee chat: Share button, header “…”, sidebar “Share link”
- Backend: `PRODUCT_V1=true` (default) skips per-document ACL for retrieval, forces upload visibility to all staff, blocks chat share APIs, and org-admin routes remain server-enforced (`403` for non-admins)

### Where the V1 flag is set (frontend)

| Location | Default | Legacy UI |
|----------|---------|-----------|
| `frontend/vite.config.ts` | `productV1Enabled` unless `VITE_PRODUCT_V1=false` at **build** time | explicit `false` |
| `infra/docker/Dockerfile.web` | `ARG VITE_PRODUCT_V1=true` | build-arg `false` |
| `docker-compose.local-prod.yml` → `web.build.args.VITE_PRODUCT_V1` | `${VITE_PRODUCT_V1:-true}` | set in repo `.env` |
| `scripts/start-web-one-port.sh` | exports `VITE_PRODUCT_V1=${VITE_PRODUCT_V1:-true}` before `npm run build` | env `false` |

Toggle full employee workspace UI only with `VITE_PRODUCT_V1=false` at build time. Set `PRODUCT_V1=false` on the API to restore legacy sharing and document visibility controls.

### Pi: rebuild web and confirm V1

```bash
cd /path/to/AQREM
git pull
docker compose -f docker-compose.local-prod.yml build --no-cache web
docker compose -f docker-compose.local-prod.yml up -d web
```

Confirm in the browser:

1. `document.documentElement.dataset.aqremUi` → `"v1"` (DevTools console)
2. `fetch('/build-info.json').then(r=>r.json())` → `product_v1: true` and a `build_id`
3. Org admin: account menu (chevron by your name) shows e.g. `UI abc1234 · V1`
4. Sidebar has no Projects/Sources/… links; no Share / header … menu; no scope pill or composer `+`
