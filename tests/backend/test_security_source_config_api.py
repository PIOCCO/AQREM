"""API: secrets in SourceCreate must not persist."""

from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.enums import EvidenceScope, SourceType
from app.models.organization import Organization, OrganizationMembership, User


def _headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def test_source_create_strips_github_token_from_config(client, db_session):
    org = Organization(name="CfgOrg", slug="cfg-org")
    db_session.add(org)
    db_session.flush()
    user = User(email="cfg@test.com", full_name="U", hashed_password=hash_password("password"))
    db_session.add(user)
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.ORG_ADMIN.value)
    )
    db_session.commit()
    token = create_access_token(str(user.id), {"organization_id": str(org.id), "role": Role.ORG_ADMIN.value})

    resp = client.post(
        "/api/v1/sources",
        headers=_headers(token, str(org.id)),
        json={
            "name": "S",
            "source_type": SourceType.GITHUB.value,
            "scope": EvidenceScope.PROJECT.value,
            "config": {"github_token": "ghp_injected", "note": "keep"},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["config"].get("github_token") in (None, "[redacted]")
    assert "ghp_injected" not in str(body["config"])
