import csv
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.enums import EvidenceScope, SourceType, SyncJobStatus
from app.models.organization import Organization, OrganizationMembership, User
from app.models.project import Project
from app.models.questionnaire import Question, Questionnaire
from app.models.source import Source, SourceSyncJob
from app.services.answering.service import AnsweringService
from app.services.ingestion.indexer import FilePayload, index_files
from app.services.questionnaire.normalize import normalize_question


def _headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


async def _seed_question_with_evidence(db_session, demo_repo_path: str):
    import uuid

    org = Organization(name="Export Org", slug=f"export-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    db_session.flush()
    project = Project(organization_id=org.id, name="SaaS Platform")
    db_session.add(project)
    db_session.flush()
    source = Source(
        organization_id=org.id,
        project_id=project.id,
        name="Demo",
        source_type=SourceType.FOLDER_ARCHIVE.value,
        scope=EvidenceScope.PROJECT.value,
    )
    db_session.add(source)
    db_session.flush()
    job = SourceSyncJob(
        organization_id=org.id, source_id=source.id, status=SyncJobStatus.RUNNING.value
    )
    db_session.add(job)
    db_session.flush()
    files = []
    root = Path(demo_repo_path)
    for path in root.rglob("*"):
        if path.is_file():
            files.append(FilePayload(relative_path=str(path.relative_to(root)), data=path.read_bytes()))
    await index_files(db_session, source=source, job=job, files=files)
    db_session.flush()
    questionnaire = Questionnaire(
        organization_id=org.id,
        project_id=project.id,
        name="Security Assessment",
    )
    db_session.add(questionnaire)
    db_session.flush()
    question = Question(
        organization_id=org.id,
        questionnaire_id=questionnaire.id,
        external_id="SEC-001",
        text="Do you encrypt customer data at rest?",
        normalized_text=normalize_question("Do you encrypt customer data at rest?"),
        sort_order=0,
    )
    db_session.add(question)
    db_session.flush()
    return org, project, question


@pytest.mark.asyncio
async def test_export_xlsx_and_csv(db_session, demo_repo_path: str, client: TestClient):
    org, project, question = await _seed_question_with_evidence(db_session, demo_repo_path)
    user = User(email="export@example.com", full_name="Export", hashed_password=hash_password("x"))
    db_session.add(user)
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.VIEWER.value)
    )
    service = AnsweringService(db_session)
    answer = await service.generate_for_question(question=question)
    await service.approve_answer(answer, user.id)
    db_session.commit()

    token = create_access_token(
        str(user.id), {"organization_id": str(org.id), "role": Role.VIEWER.value}
    )
    qid = question.questionnaire_id
    xlsx = client.get(
        f"/api/v1/questionnaires/{qid}/export/xlsx",
        headers=_headers(token, str(org.id)),
    )
    assert xlsx.status_code == 200
    assert "spreadsheetml" in xlsx.headers["content-type"]
    assert len(xlsx.content) > 100

    csv_resp = client.get(
        f"/api/v1/questionnaires/{qid}/export/csv",
        headers=_headers(token, str(org.id)),
    )
    assert csv_resp.status_code == 200
    text = csv_resp.content.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0][0] == "Question ID"
    assert any("SEC-001" in row[0] for row in rows[1:])

    approved = client.get(
        f"/api/v1/questionnaires/{qid}/export/csv?approved_only=true",
        headers=_headers(token, str(org.id)),
    )
    assert approved.status_code == 200
    approved_rows = list(csv.reader(io.StringIO(approved.content.decode("utf-8-sig"))))
    assert len(approved_rows) == 2  # header + one approved row


def test_export_tenant_isolation(client: TestClient, db_session):
    org1 = Organization(name="E1", slug="export-org-1")
    org2 = Organization(name="E2", slug="export-org-2")
    user1 = User(email="e1@example.com", full_name="E1", hashed_password=hash_password("x"))
    db_session.add_all([org1, org2, user1])
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org1.id, user_id=user1.id, role=Role.VIEWER.value)
    )
    from app.models.questionnaire import Questionnaire

    qn = Questionnaire(organization_id=org2.id, name="Secret")
    db_session.add(qn)
    db_session.commit()

    token = create_access_token(str(user1.id), {"organization_id": str(org1.id), "role": Role.VIEWER.value})
    resp = client.get(
        f"/api/v1/questionnaires/{qn.id}/export/csv",
        headers=_headers(token, str(org1.id)),
    )
    assert resp.status_code == 404


def test_viewer_can_export(client: TestClient, db_session):
    org = Organization(name="Viewer Export", slug="viewer-export")
    user = User(email="ve@example.com", full_name="VE", hashed_password=hash_password("x"))
    db_session.add_all([org, user])
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.VIEWER.value)
    )
    from app.models.questionnaire import Questionnaire

    qn = Questionnaire(organization_id=org.id, name="Empty Export")
    db_session.add(qn)
    db_session.commit()
    token = create_access_token(str(user.id), {"organization_id": str(org.id), "role": Role.VIEWER.value})
    resp = client.get(
        f"/api/v1/questionnaires/{qn.id}/export/xlsx",
        headers=_headers(token, str(org.id)),
    )
    assert resp.status_code == 200
