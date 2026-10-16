# Pi / local Compose: least-privilege database roles (RLS active)

`docker-compose.local-prod.yml` now connects api/worker/beat as `aqrem_app` (control plane) and
`aqrem_tenant` (org-scoped data plane), and runs migrations as `aqrem_migrator`. `aqrem` remains the
Postgres superuser for administration only (and for the model-gateway container, unchanged).

## Existing Pi database (one time)
```bash
cd ~/AQREM-azure && git pull
# add three URL-safe passwords to .env
for v in AQREM_MIGRATOR_DB_PASSWORD AQREM_APP_DB_PASSWORD AQREM_TENANT_DB_PASSWORD; do
  grep -q "^$v=." .env || echo "$v=$(openssl rand -hex 24)" >> .env; done
docker compose -f docker-compose.local-prod.yml up -d postgres
./scripts/pi-db-least-privilege.sh          # safety pg_dump, roles, ownership -> aqrem_migrator, grants
docker compose -f docker-compose.local-prod.yml up -d --build --force-recreate api worker worker-beat
docker compose -f docker-compose.local-prod.yml logs api | grep -E "Migrations applied|Startup"
docker compose -f docker-compose.local-prod.yml exec -T api python -m app.db.rls status   # expect 36/36
docker compose -f docker-compose.local-prod.yml exec -T postgres psql -U aqrem -d aqrem -c \
  "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname LIKE 'aqrem%'"
```
A fresh volume runs `infra/dev/postgres/init/02-least-privilege.sh` automatically.

## Verify the full flow as least-privilege roles (same check that was run on the dev box)
Inside the api container (uses the compose Postgres, a throwaway database `aqrem_lp_verify`):
```bash
docker compose -f docker-compose.local-prod.yml exec -T -e ADMIN_PG=postgresql://aqrem:aqrem@postgres:5432 \
  api bash /app/scripts/verify-least-privilege-local.sh
```
(needs `psql`/`openssl` in the image; otherwise run it on the Pi host with a venv:
`ADMIN_PG=postgresql://aqrem:aqrem@127.0.0.1:5432 ./scripts/verify-least-privilege-local.sh`).
The container already has `AQREM_*_DB_PASSWORD` from `.env` (env_file), so the role passwords are reused, not
changed. On the host run `set -a; . ./.env; set +a` first for the same effect. Expected output ends with
`ALL 22 STEPS PASSED` and `legacy org still present: 1`.

## Undo
`python -m app.db.rls disable` (as migrator) and point `DATABASE_URL` back to `aqrem` - see docs/migrations.md.
