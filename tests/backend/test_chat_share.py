from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.roles import Role
from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN
from app.core.security import create_access_token, hash_password
from app.models.chat_share import ChatConversationShare
from app.models.organization import Organization, OrganizationMembership, User


def _auth_headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def _seed_org_user(db_session, slug: str, email: str, *, enable_sharing: bool = True):
    org = Organization(
        name=f"Org {slug}",
        slug=slug,
        license_limit=5,
        chat_shares_enabled=enable_sharing,
        chat_share_ttl_days=7,
    )
    db_session.add(org)
    db_session.flush()
    user = User(email=email, hashed_password=hash_password("password"), full_name="User")
    db_session.add(user)
    db_session.flush()
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.EDITOR.value))
    db_session.flush()
    token = create_access_token(
        str(user.id),
        {"organization_id": str(org.id), "role": Role.EDITOR.value, "auth_version": 1},
        audience=AUD_EMPLOYEE,
    )
    return org, user, token


def test_create_and_fetch_share_same_org(client: TestClient, db_session):
    org, _user, token = _seed_org_user(db_session, "share-a", "share-a@example.com")
    headers = _auth_headers(token, str(org.id))
    payload = {
        "client_conversation_id": "local-conv-1",
        "title": "Security review",
        "messages": [{"role": "user", "content": "Hello", "created_at": "2026-01-01T00:00:00Z"}],
    }
    create = client.post("/api/v1/chat/shares", headers=headers, json=payload)
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["share_token"]
    assert body["share_path"].startswith("/share/")

    share_token = body["share_token"]
    get_res = client.get(f"/api/v1/chat/shares/{share_token}", headers=headers)
    assert get_res.status_code == 200
    view = get_res.json()
    assert view["title"] == "Security review"
    assert view["messages"][0]["content"] == "Hello"

    public = client.get(f"/api/v1/public/chat/shares/{share_token}")
    assert public.status_code == 200
    assert public.headers.get("x-robots-tag") == "noindex, nofollow"


def test_share_disabled_by_default(client: TestClient, db_session):
    org, _, token = _seed_org_user(db_session, "share-off", "off@example.com", enable_sharing=False)
    res = client.post(
        "/api/v1/chat/shares",
        headers=_auth_headers(token, str(org.id)),
        json={"client_conversation_id": "x", "title": "T", "messages": []},
    )
    assert res.status_code == 403


def test_share_not_accessible_from_other_org(client: TestClient, db_session):
    org_a, _, token_a = _seed_org_user(db_session, "share-b1", "b1@example.com")
    org_b, _, token_b = _seed_org_user(db_session, "share-b2", "b2@example.com")
    create = client.post(
        "/api/v1/chat/shares",
        headers=_auth_headers(token_a, str(org_a.id)),
        json={
            "client_conversation_id": "conv-x",
            "title": "Private",
            "messages": [{"role": "user", "content": "secret"}],
        },
    )
    assert create.status_code == 201
    share_token = create.json()["share_token"]
    denied = client.get(f"/api/v1/chat/shares/{share_token}", headers=_auth_headers(token_b, str(org_b.id)))
    assert denied.status_code == 404
    assert client.get(f"/api/v1/public/chat/shares/{share_token}").status_code == 200


def test_guessed_token_returns_404(client: TestClient, db_session):
    org, _, token = _seed_org_user(db_session, "share-c", "c@example.com")
    res = client.get(
        "/api/v1/chat/shares/not-a-real-token-value",
        headers=_auth_headers(token, str(org.id)),
    )
    assert res.status_code == 404
    assert client.get("/api/v1/public/chat/shares/not-a-real-token-value").status_code == 404


def test_revoke_blocks_access(client: TestClient, db_session):
    org, user, token = _seed_org_user(db_session, "share-d", "d@example.com")
    headers = _auth_headers(token, str(org.id))
    create = client.post(
        "/api/v1/chat/shares",
        headers=headers,
        json={"client_conversation_id": "c1", "title": "T", "messages": []},
    )
    share_token = create.json()["share_token"]
    revoke = client.delete(f"/api/v1/chat/shares/{share_token}", headers=headers)
    assert revoke.status_code == 204
    get_res = client.get(f"/api/v1/chat/shares/{share_token}", headers=headers)
    assert get_res.status_code == 404
    assert client.get(f"/api/v1/public/chat/shares/{share_token}").status_code == 404


def test_expired_share_returns_404(client: TestClient, db_session):
    org, _, token = _seed_org_user(db_session, "share-exp", "exp@example.com")
    headers = _auth_headers(token, str(org.id))
    create = client.post(
        "/api/v1/chat/shares",
        headers=headers,
        json={"client_conversation_id": "c-exp", "title": "Old", "messages": []},
    )
    share_token = create.json()["share_token"]
    share = db_session.query(ChatConversationShare).filter(ChatConversationShare.share_token == share_token).one()
    share.expires_at = datetime.now(UTC) - timedelta(minutes=5)
    db_session.commit()
    assert client.get(f"/api/v1/public/chat/shares/{share_token}").status_code == 404


def test_create_share_requires_auth(client: TestClient):
    res = client.post("/api/v1/chat/shares", json={"client_conversation_id": "x", "title": "T", "messages": []})
    assert res.status_code == 401
