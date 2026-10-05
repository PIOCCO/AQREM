from fastapi.testclient import TestClient

from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.enums import SourceType
from app.models.organization import Organization, OrganizationMembership, User
from app.models.source import Source


def _auth_headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def test_create_project_with_initial_source(client: TestClient, db_session):
    org = Organization(name="Acme", slug="acme-proj-src")
    user = User(email="proj@example.com", full_name="P", hashed_password=hash_password("password"))
    db_session.add_all([org, user])
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.ORG_ADMIN.value)
    )
    db_session.commit()

    token = create_access_token(str(user.id), {"organization_id": str(org.id), "role": Role.ORG_ADMIN.value})
    resp = client.post(
        "/api/v1/projects",
        headers=_auth_headers(token, str(org.id)),
        json={
            "name": "Unified Project",
            "description": "With source",
            "initial_source": {
                "name": "Demo folder",
                "source_type": SourceType.FOLDER_ARCHIVE.value,
                "config": {"demo_path": "/tmp/demo"},
            },
        },
    )
    assert resp.status_code == 200, resp.text
    project_id = resp.json()["id"]

    sources = db_session.query(Source).filter(Source.project_id == project_id).all()
    assert len(sources) == 1
    assert sources[0].name == "Demo folder"
    assert sources[0].config.get("demo_path") == "/tmp/demo"
