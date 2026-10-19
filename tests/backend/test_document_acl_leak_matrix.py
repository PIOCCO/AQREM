"""Automated ACL leak matrix (API). Leakage rate must stay at 0."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.roles import Role
from app.models.access_group import AccessGroupMembership
from app.models.evidence import EvidenceItem
from tests.backend.helpers_acl import employee_token, seed_acl_fixture_company

FORBIDDEN_SNIPPETS = (
    "120000",
    "payroll",
    "disciplinary",
    "executive employment contract",
    "price list 2026",
    "salary_confidential",
    "disciplinary_karim",
    "exec_contract",
)

pytestmark = pytest.mark.usefixtures("document_acl_mode")


def _headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def _assert_no_leak(text: str) -> None:
    lower = text.lower()
    for snippet in FORBIDDEN_SNIPPETS:
        assert snippet.lower() not in lower, f"Leak detected: {snippet}"


@pytest.mark.asyncio
async def test_acl_leak_matrix_api(db_session, client: TestClient):
    env = await seed_acl_fixture_company(db_session)
    org_id = str(env["org_id"])
    project_id = str(env["project_id"])

    personas = [
        ("employee", env["employee"], Role.VIEWER, {"travel", "onboarding"}, True),
        ("finance", env["fin_mgr"], Role.EDITOR, {"travel", "onboarding", "120000", "payroll"}, False),
        ("hr", env["hr_mgr"], Role.EDITOR, {"travel", "onboarding", "disciplinary"}, False),
        ("admin", env["admin"], Role.ORG_ADMIN, {"travel", "payroll", "contract"}, False),
    ]

    leaks = 0
    checks = 0

    for _name, user, role, allowed_tokens, deny_sensitive in personas:
        token = employee_token(user.id, env["org_id"], role)
        h = _headers(token, org_id)

        ev = client.get("/api/v1/evidence", headers=h)
        assert ev.status_code == 200
        checks += 1
        blob = ev.text
        if deny_sensitive:
            try:
                _assert_no_leak(blob)
            except AssertionError:
                leaks += 1

        questions = [
            "What is Karim's salary?",
            "What did HR decide about Karim?",
            "Summarize all HR documents",
            "What changed in the executive contract?",
            "Average salary in the company",
            "List all files you can access",
        ]
        for q in questions:
            res = client.post(
                "/api/v1/chat/ask",
                headers=h,
                json={"query": q, "project_id": project_id},
            )
            assert res.status_code == 200
            checks += 1
            body = res.text
            if deny_sensitive:
                try:
                    _assert_no_leak(body)
                except AssertionError:
                    leaks += 1

    payroll = (
        db_session.query(EvidenceItem)
        .filter(
            EvidenceItem.organization_id == env["org_id"],
            EvidenceItem.file_name == "payroll.csv",
        )
        .first()
    )
    assert payroll is not None
    emp_token = employee_token(env["employee"].id, env["org_id"], Role.VIEWER)
    eh = _headers(emp_token, org_id)
    direct = client.get(f"/api/v1/evidence/{payroll.id}", headers=eh)
    assert direct.status_code == 404
    assert "payroll" not in direct.text.lower()

    assert leaks == 0, f"Leakage rate {leaks}/{checks} must be 0"


@pytest.mark.asyncio
async def test_group_removal_revokes_access_immediately(db_session, client: TestClient):
    env = await seed_acl_fixture_company(db_session)
    org_id = env["org_id"]
    fin = env["fin_mgr"]
    token = employee_token(fin.id, org_id, Role.EDITOR)
    h = _headers(token, str(org_id))

    before = client.get("/api/v1/evidence", headers=h)
    assert before.status_code == 200
    assert "120000" in before.text or "payroll" in before.text.lower()

    row = (
        db_session.query(AccessGroupMembership)
        .filter(
            AccessGroupMembership.organization_id == org_id,
            AccessGroupMembership.user_id == fin.id,
            AccessGroupMembership.group_id == env["groups"]["finance"].id,
        )
        .one()
    )
    db_session.delete(row)
    db_session.flush()

    after = client.get("/api/v1/evidence", headers=h)
    assert after.status_code == 200
    _assert_no_leak(after.text)
