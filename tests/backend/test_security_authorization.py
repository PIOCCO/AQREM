from fastapi.testclient import TestClient

from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.organization import Organization, OrganizationMembership, User
from app.models.project import Project


def _headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def test_cannot_read_other_org_project(client: TestClient, db_session):
    org1 = Organization(name="Org1", slug="sec-o1")
    org2 = Organization(name="Org2", slug="sec-o2")
    user1 = User(email="sec1@example.com", full_name="U1", hashed_password=hash_password("password"))
    db_session.add_all([org1, org2, user1])
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org1.id, user_id=user1.id, role=Role.ORG_ADMIN.value)
    )
    secret_project = Project(organization_id=org2.id, name="Secret")
    db_session.add(secret_project)
    db_session.commit()

    token = create_access_token(str(user1.id), {"organization_id": str(org1.id), "role": Role.ORG_ADMIN.value})
    resp = client.get(f"/api/v1/projects/{secret_project.id}", headers=_headers(token, str(org1.id)))
    assert resp.status_code == 404


def test_cannot_list_other_org_project_in_summaries(client: TestClient, db_session):
    org1 = Organization(name="OrgA", slug="sec-a")
    org2 = Organization(name="OrgB", slug="sec-b")
    user1 = User(email="sec2@example.com", full_name="U2", hashed_password=hash_password("password"))
    db_session.add_all([org1, org2, user1])
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org1.id, user_id=user1.id, role=Role.VIEWER.value)
    )
    db_session.add(Project(organization_id=org2.id, name="Hidden"))
    db_session.commit()

    token = create_access_token(str(user1.id), {"organization_id": str(org1.id), "role": Role.VIEWER.value})
    resp = client.get("/api/v1/projects/summaries", headers=_headers(token, str(org1.id)))
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "Hidden" not in names
