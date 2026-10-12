"""Source create must not attach to another organization's project."""

from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.enums import EvidenceScope, SourceType
from app.models.organization import Organization, OrganizationMembership, User
from app.models.project import Project


def _headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def test_source_create_rejects_foreign_project(client, db_session):
    org_a = Organization(name="Org A", slug="org-a", license_limit=5)
    org_b = Organization(name="Org B", slug="org-b", license_limit=5)
    db_session.add_all([org_a, org_b])
    db_session.flush()

    project_b = Project(organization_id=org_b.id, name="B Project", description="")
    db_session.add(project_b)
    db_session.flush()

    user = User(email="editor@test.com", full_name="Editor", hashed_password=hash_password("password"))
    db_session.add(user)
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org_a.id, user_id=user.id, role=Role.EDITOR.value)
    )
    db_session.commit()

    token = create_access_token(str(user.id), {"organization_id": str(org_a.id), "role": Role.EDITOR.value})
    resp = client.post(
        "/api/v1/sources",
        headers=_headers(token, str(org_a.id)),
        json={
            "name": "Cross-org source",
            "source_type": SourceType.FOLDER_ARCHIVE.value,
            "scope": EvidenceScope.PROJECT.value,
            "project_id": str(project_b.id),
            "config": {},
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid project"
