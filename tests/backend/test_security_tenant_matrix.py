"""Cross-tenant access attempts (User A must not read Tenant B resources)."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.enums import EvidenceScope, SourceType
from app.models.evidence import EvidenceItem
from app.models.organization import Organization, OrganizationMembership, User
from app.models.project import Project
from app.models.questionnaire import Answer, Question, Questionnaire
from app.models.source import Source
from app.services.questionnaire.normalize import normalize_question


def _headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def _seed_tenant_b(db_session):
    org_b = Organization(name="TenantB", slug="tenant-b-sec")
    db_session.add(org_b)
    db_session.flush()
    project_b = Project(organization_id=org_b.id, name="B Project")
    db_session.add(project_b)
    db_session.flush()

    source_b = Source(
        organization_id=org_b.id,
        project_id=project_b.id,
        name="B Source",
        source_type=SourceType.FOLDER_ARCHIVE.value,
        scope=EvidenceScope.PROJECT.value,
    )
    db_session.add(source_b)
    db_session.flush()

    evidence_b = EvidenceItem(
        organization_id=org_b.id,
        project_id=project_b.id,
        source_id=source_b.id,
        source_type=source_b.source_type,
        scope=source_b.scope,
        file_name="secret.txt",
        file_path="secret.txt",
        content="Tenant B confidential evidence",
        content_hash="hash-b",
    )
    db_session.add(evidence_b)

    qn_b = Questionnaire(organization_id=org_b.id, name="B Q", project_id=project_b.id)
    db_session.add(qn_b)
    db_session.flush()
    q_b = Question(
        organization_id=org_b.id,
        questionnaire_id=qn_b.id,
        external_id="B1",
        text="Secret question?",
        normalized_text=normalize_question("Secret question?"),
        sort_order=0,
    )
    db_session.add(q_b)
    db_session.flush()
    ans_b = Answer(
        organization_id=org_b.id,
        question_id=q_b.id,
        draft_text="Tenant B answer",
        potentially_stale=True,
    )
    db_session.add(ans_b)
    db_session.commit()
    return org_b, project_b, source_b, evidence_b, qn_b, q_b, ans_b


def _user_a(db_session, org_a: Organization) -> tuple[User, str]:
    user_a = User(email="usera@sec.test", full_name="A", hashed_password=hash_password("password"))
    db_session.add(user_a)
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org_a.id, user_id=user_a.id, role=Role.ORG_ADMIN.value)
    )
    db_session.commit()
    token = create_access_token(str(user_a.id), {"organization_id": str(org_a.id), "role": Role.ORG_ADMIN.value})
    return user_a, token


def test_tenant_a_cannot_access_tenant_b_resources(client: TestClient, db_session):
    org_a = Organization(name="TenantA", slug="tenant-a-sec")
    db_session.add(org_a)
    db_session.flush()
    _, token_a = _user_a(db_session, org_a)

    org_b, project_b, source_b, evidence_b, qn_b, q_b, ans_b = _seed_tenant_b(db_session)

    h = _headers(token_a, str(org_a.id))
    assert client.get(f"/api/v1/projects/{project_b.id}", headers=h).status_code == 404
    assert client.get("/api/v1/sources", headers=h).json() == [] or all(
        s.get("organization_id") == str(org_a.id) for s in client.get("/api/v1/sources", headers=h).json()
    )
    sync = client.post(f"/api/v1/sources/{source_b.id}/sync", headers=h)
    assert sync.status_code in {403, 404}
    assert client.get(f"/api/v1/evidence/{evidence_b.id}", headers=h).status_code == 404
    assert client.get(f"/api/v1/questionnaires/{qn_b.id}", headers=h).status_code == 404
    assert client.get(f"/api/v1/questionnaires/questions/{q_b.id}", headers=h).status_code == 404
    detail = client.get(f"/api/v1/stale-answers/{ans_b.id}", headers=h)
    assert detail.status_code in {403, 404}

    preview = client.post(
        "/api/v1/retrieval/preview",
        headers=h,
        json={"query": "confidential", "project_id": str(project_b.id)},
    )
    assert preview.status_code == 200
    ids = {item["id"] for item in preview.json().get("items", [])}
    assert str(evidence_b.id) not in ids
