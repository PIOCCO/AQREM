"""End-to-end check that AQREM works when connected ONLY as least-privilege roles (RLS enforced).

Usage (env must point at a database prepared by scripts/sql/least-privilege-roles.sql):
    MIGRATION_DATABASE_URL=...aqrem_migrator...  DATABASE_URL=...aqrem_app...  TENANT_DATABASE_URL=...aqrem_tenant...
    PLATFORM_ADMIN_EMAIL=... PLATFORM_ADMIN_PASSWORD=...  python scripts/verify_least_privilege_flow.py

Steps: startup (migrations as migrator, bootstrap as app) -> platform admin login -> create 2 orgs via API ->
org users -> login by email -> upload a document per org -> Celery run_source_sync invoked directly ->
retrieval preview + chat ask (no cross-org content) -> beat task sweep_stuck_documents -> audit retention ->
scheduled org purge -> asserts the runtime connections are not superuser/BYPASSRLS. Broker calls are captured
in-process (no Redis needed); LLM_PROVIDER=mock. Exit code 0 = all steps passed.
"""
from __future__ import annotations

import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

STEPS: list[tuple[str, bool, str]] = []


def step(name: str, ok: bool, detail: str = "") -> None:
    STEPS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{(' - ' + detail) if detail else ''}", flush=True)
    if not ok:
        raise SystemExit(1)


def main() -> int:
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    import app.services.ingestion.enqueue as enqueue_mod
    from app.celery_app import celery_app
    from app.main import create_app

    queued: list[list[str]] = []
    import app.core.broker_health as bh

    bh.assert_broker_available = lambda: None
    enqueue_mod.assert_broker_available = lambda: None
    celery_app.send_task = lambda name, args=None, **kw: queued.append(list(args or []))  # type: ignore[assignment]

    with TestClient(create_app()) as client:
        from app.db.session import SessionLocal

        with SessionLocal() as s:
            who = s.execute(text("SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")).one()
        step("control connection is least-privilege", who[1] is False and who[2] is False, f"user={who[0]}")
        ver = s  # noqa: F841
        r = client.post("/api/v1/auth/login", json={"email": os.environ["PLATFORM_ADMIN_EMAIL"],
                                                     "password": os.environ["PLATFORM_ADMIN_PASSWORD"]})
        step("platform admin login (cross-org identity lookup)", r.status_code == 200, str(r.status_code))
        ptok = r.json()["access_token"]
        P = {"Authorization": f"Bearer {ptok}"}

        orgs = {}
        from app.core.roles import Role
        from app.core.security import hash_password
        from app.models.organization import OrganizationMembership, User

        for key, marker in (("a", "ALPHA-LP-7731 retention is 30 days"), ("b", "BRAVO-LP-9920 retention is 90 days")):
            r = client.post("/api/v1/admin/organizations", headers=P,
                            json={"name": f"LP Org {key} {uuid.uuid4().hex[:4]}", "license_limit": 10,
                                  "environment": "production"})
            step(f"create org {key} via admin API", r.status_code == 201, f"{r.status_code} {r.text[:200] if r.status_code != 201 else ''}")
            org_id = r.json()["id"]
            pw = uuid.uuid4().hex
            with SessionLocal() as s:  # stands in for invitation acceptance (control plane)
                admin = User(email=f"lp-admin-{key}-{uuid.uuid4().hex[:6]}@example.com", full_name=f"Admin {key}",
                             hashed_password=hash_password(pw), is_active=True)
                emp = User(email=f"lp-emp-{key}-{uuid.uuid4().hex[:6]}@example.com", full_name=f"Emp {key}",
                           hashed_password=hash_password(pw), is_active=True)
                s.add_all([admin, emp]); s.flush()
                s.add_all([OrganizationMembership(organization_id=org_id, user_id=admin.id, role=Role.ORG_ADMIN.value),
                           OrganizationMembership(organization_id=org_id, user_id=emp.id, role=Role.EDITOR.value)])
                s.commit()
                admin_email, emp_email = admin.email, emp.email
            toks = {}
            for who_, email in (("admin", admin_email), ("emp", emp_email)):
                r = client.post("/api/v1/auth/login", json={"email": email, "password": pw})
                step(f"login by email org {key} {who_}", r.status_code == 200, str(r.status_code))
                toks[who_] = r.json()["access_token"]
            H = {"Authorization": f"Bearer {toks['admin']}", "X-Organization-Id": org_id}
            queued.clear()
            r = client.post("/api/v1/org-admin/documents/upload", headers=H, data={"visibility_mode": "all_staff"},
                            files=[("files", ("policy.txt", (marker + "\n") * 5, "text/plain"))])
            step(f"upload document org {key}", r.status_code in (200, 201) and queued, f"{r.status_code} queued={len(queued)} {r.text[:300] if r.status_code >= 300 else ''}")
            from app.tasks.ingestion import run_source_sync

            for job_id, oid in list(queued):
                res = run_source_sync(job_id, oid)  # the Celery task body, as the worker runs it
                step(f"celery run_source_sync org {key}", not (res or {}).get("error"), str(res)[:200])
            r = client.get("/api/v1/org-admin/documents", headers=H)
            docs = r.json() if r.status_code == 200 else {}
            items = docs.get("items", docs) if isinstance(docs, dict) else docs
            statuses = [d.get("status") for d in items] if isinstance(items, list) else []
            step(f"document indexed org {key}", "indexed" in statuses, f"{r.status_code} {statuses}")
            orgs[key] = {"id": org_id, "emp": toks["emp"], "admin": toks["admin"], "marker": marker.split()[0]}

        for key, other in (("a", "b"), ("b", "a")):
            E = {"Authorization": f"Bearer {orgs[key]['emp']}", "X-Organization-Id": orgs[key]["id"]}
            r = client.post("/api/v1/chat/ask", headers=E, json={"query": "what is the retention period?"})
            body = r.text
            step(f"chat ask org {key}", r.status_code == 200 and orgs[other]["marker"] not in body,
                 f"{r.status_code} own_marker_present={orgs[key]['marker'] in body}")
            r = client.post("/api/v1/retrieval/preview", headers=E, json={"query": "retention period", "limit": 10})
            step(f"retrieval preview org {key} no cross-org", r.status_code in (200, 403) and orgs[other]["marker"] not in r.text,
                 f"{r.status_code} own_marker_present={orgs[key]['marker'] in r.text}")

        from app.tasks.maintenance import sweep_stuck_documents

        res = sweep_stuck_documents()
        step("beat task sweep_stuck_documents", res.get("orgs", 0) >= 2, str(res))
        from app.services.audit.org_cleanup import run_audit_retention_all_orgs

        n = run_audit_retention_all_orgs(1)
        step("audit retention (all orgs, tenant role)", True, f"removed={n}")
        from datetime import UTC, datetime, timedelta

        from app.db.rls import scope_session_to_org
        from app.models.organization import Organization
        from app.services.org_lifecycle import run_scheduled_org_purges

        b_id = uuid.UUID(orgs["b"]["id"])
        with SessionLocal() as s:  # org B soft-deleted with an elapsed retention window
            org_b = s.get(Organization, b_id)
            org_b.deleted_at = datetime.now(UTC) - timedelta(days=40)
            org_b.purge_scheduled_at = datetime.now(UTC) - timedelta(minutes=1)
            s.commit()
        with SessionLocal() as s:
            purged = run_scheduled_org_purges(s)
            s.commit()
        with SessionLocal() as s:
            scope_session_to_org(s, b_id)
            left = s.execute(text("SELECT count(*) FROM evidence_items")).scalar()
            still = s.execute(text("SELECT count(*) FROM organizations WHERE id = :o"), {"o": b_id}).scalar()
            scope_session_to_org(s, uuid.UUID(orgs["a"]["id"]))
            a_left = s.execute(text("SELECT count(*) FROM evidence_items")).scalar()
        step("scheduled org purge removes org B data only", purged == 1 and left == 0 and still == 0 and a_left > 0,
             f"purged={purged} b_chunks={left} b_org_rows={still} a_chunks={a_left}")
        from app.tenant_store.pool import tenant_pool_manager

        with SessionLocal() as control:
            from app.tenant_store.resolver import open_tenant_session

            t = open_tenant_session(control, uuid.UUID(orgs["a"]["id"]))
            row = t.execute(text("SELECT current_user, (SELECT rolbypassrls FROM pg_roles WHERE rolname=current_user), "
                                 "current_setting('app.current_org', true)")).one()
            cnt_other = t.execute(text("SELECT count(*) FROM evidence_items WHERE organization_id = CAST(:o AS uuid)"),
                                  {"o": orgs["b"]["id"]}).scalar()
            t.close()
        step("tenant connection role + org scope", row[1] is False and row[2] == orgs["a"]["id"] and cnt_other == 0,
             f"user={row[0]} other_org_rows={cnt_other}")
        tenant_pool_manager.dispose_all()
    print(f"ALL {len(STEPS)} STEPS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
