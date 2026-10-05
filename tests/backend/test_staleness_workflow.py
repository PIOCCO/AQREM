from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.enums import AnswerGenerationSource, AnswerStatus
from app.models.organization import Organization, OrganizationMembership, User
from app.models.questionnaire import Answer
from app.models.staleness import AnswerStalenessEvent
from app.services.answering.service import AnsweringService
from app.services.staleness.service import StalenessService
from app.models.enums import EvidenceScope, SourceType, SyncJobStatus
from app.models.project import Project
from app.models.questionnaire import Question, Questionnaire
from app.models.source import Source, SourceSyncJob
from app.services.ingestion.indexer import FilePayload, index_files
from app.services.questionnaire.normalize import normalize_question


def _headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


@pytest.mark.asyncio
async def test_stale_detection_on_evidence_change(db_session, demo_repo_path: str):
    org, project, question = await _seed_question_with_evidence(db_session, demo_repo_path)
    user = User(email="stale1@example.com", full_name="Stale", hashed_password=hash_password("x"))
    db_session.add(user)
    db_session.flush()
    service = AnsweringService(db_session)
    answer = await service.generate_for_question(question=question)
    await service.approve_answer(answer, user.id)
    db_session.flush()

    from app.models.source import Source, SourceSyncJob
    from app.models.enums import SyncJobStatus, SourceType
    from app.services.ingestion.indexer import FilePayload, index_files

    source = db_session.query(Source).filter(Source.project_id == project.id).first()
    job = SourceSyncJob(organization_id=org.id, source_id=source.id, status=SyncJobStatus.RUNNING.value)
    db_session.add(job)
    db_session.flush()
    await index_files(
        db_session,
        source=source,
        job=job,
        files=[
            FilePayload(
                relative_path="docs/architecture.md",
                data=b"# changed\n\nEncryption removed from documentation.",
            )
        ],
    )
    db_session.flush()
    db_session.refresh(answer)
    assert answer.potentially_stale is True
    assert (
        db_session.query(AnswerStalenessEvent).filter(AnswerStalenessEvent.answer_id == answer.id).count()
        >= 1
    )


@pytest.mark.asyncio
async def test_revalidate_clears_when_evidence_restored(db_session, demo_repo_path: str):
    org, project, question = await _seed_question_with_evidence(db_session, demo_repo_path)
    user = User(email="stale2@example.com", full_name="Stale", hashed_password=hash_password("x"))
    db_session.add(user)
    db_session.flush()
    answer_service = AnsweringService(db_session)
    answer = await answer_service.generate_for_question(question=question)
    await answer_service.approve_answer(answer, user.id)
    db_session.flush()

    from app.models.answer_library import AnswerLibraryEntry, AnswerLibraryEvidenceLink
    from app.models.evidence import EvidenceItem

    entry = (
        db_session.query(AnswerLibraryEntry)
        .filter(AnswerLibraryEntry.source_answer_id == answer.id)
        .first()
    )
    assert entry is not None
    link = (
        db_session.query(AnswerLibraryEvidenceLink)
        .filter(AnswerLibraryEvidenceLink.library_entry_id == entry.id)
        .first()
    )
    assert link is not None
    item = db_session.get(EvidenceItem, link.evidence_item_id)
    assert item is not None

    event = AnswerStalenessEvent(
        organization_id=org.id,
        answer_id=answer.id,
        evidence_item_id=item.id,
        file_path=link.file_path,
        snapshot_content_hash=link.snapshot_content_hash,
        current_content_hash="changed-hash",
        reason="test",
        status="open",
    )
    answer.potentially_stale = True
    answer.status = AnswerStatus.NEEDS_REVIEW.value
    db_session.add(event)
    db_session.flush()

    result = StalenessService(db_session).revalidate(
        organization_id=org.id, answer_id=answer.id, user_id=user.id
    )
    assert result["current"] is True
    db_session.refresh(answer)
    assert answer.potentially_stale is False


@pytest.mark.asyncio
async def test_revalidate_reports_changed_evidence(db_session, demo_repo_path: str):
    org, project, question = await _seed_question_with_evidence(db_session, demo_repo_path)
    answer_service = AnsweringService(db_session)
    answer = await answer_service.generate_for_question(question=question)
    answer.potentially_stale = True
    answer.status = AnswerStatus.NEEDS_REVIEW.value
    db_session.add(
        AnswerStalenessEvent(
            organization_id=org.id,
            answer_id=answer.id,
            file_path="docs/architecture.md",
            snapshot_content_hash="old",
            current_content_hash="new",
            reason="changed",
            status="open",
        )
    )
    db_session.flush()
    result = StalenessService(db_session).revalidate(
        organization_id=org.id, answer_id=answer.id, user_id=None
    )
    assert result["current"] is False
    assert result["status"] == AnswerStatus.NEEDS_REVIEW.value


@pytest.mark.asyncio
async def test_stale_library_entry_not_reused(db_session, demo_repo_path: str):
    org, project, question = await _seed_question_with_evidence(db_session, demo_repo_path)
    user = User(email="stale3@example.com", full_name="Stale", hashed_password=hash_password("x"))
    db_session.add(user)
    db_session.flush()
    answer_service = AnsweringService(db_session)
    first = await answer_service.generate_for_question(question=question)
    await answer_service.approve_answer(first, user.id)
    db_session.flush()

    from app.models.questionnaire import Question, Questionnaire
    from app.services.questionnaire.normalize import normalize_question

    questionnaire = db_session.get(Questionnaire, question.questionnaire_id)
    q2 = Question(
        organization_id=org.id,
        questionnaire_id=questionnaire.id,
        external_id="SEC-002",
        text="Do you encrypt customer data at rest?",
        normalized_text=normalize_question("Do you encrypt customer data at rest?"),
        sort_order=1,
    )
    db_session.add(q2)
    db_session.flush()
    from app.models.source import Source, SourceSyncJob
    from app.models.enums import SyncJobStatus
    from app.services.ingestion.indexer import FilePayload, index_files

    source = db_session.query(Source).filter(Source.project_id == project.id).first()
    job = SourceSyncJob(organization_id=org.id, source_id=source.id, status=SyncJobStatus.RUNNING.value)
    db_session.add(job)
    db_session.flush()
    await index_files(
        db_session,
        source=source,
        job=job,
        files=[
            FilePayload(
                relative_path="docs/architecture.md",
                data=b"# Architecture\n\nEncryption statement removed.",
            )
        ],
    )
    db_session.refresh(first)
    assert first.potentially_stale is True

    second = await answer_service.generate_for_question(question=q2)
    assert second.generation_source == AnswerGenerationSource.RETRIEVAL_LLM.value


@pytest.mark.asyncio
async def test_stale_regeneration_uses_current_evidence(db_session, demo_repo_path: str):
    org, project, question = await _seed_question_with_evidence(db_session, demo_repo_path)
    answer_service = AnsweringService(db_session)
    answer = await answer_service.generate_for_question(question=question)
    answer.approved_text = "Previously approved text"
    answer.potentially_stale = True
    db_session.flush()

    regenerated = await answer_service.generate_for_question(
        question=question,
        skip_library_reuse=True,
        stale_regeneration=True,
    )
    assert regenerated.generation_source == AnswerGenerationSource.STALE_REGENERATION.value
    assert regenerated.approved_text == "Previously approved text"
    assert regenerated.draft_text


@pytest.mark.asyncio
async def test_approval_after_regeneration_clears_stale(db_session, demo_repo_path: str):
    org, project, question = await _seed_question_with_evidence(db_session, demo_repo_path)
    user = User(email="stale4@example.com", full_name="Stale", hashed_password=hash_password("x"))
    db_session.add(user)
    db_session.flush()
    answer_service = AnsweringService(db_session)
    answer = await answer_service.generate_for_question(question=question)
    answer.potentially_stale = True
    db_session.flush()
    await answer_service.approve_answer(answer, user.id)
    db_session.refresh(answer)
    assert answer.potentially_stale is False
    assert answer.status == AnswerStatus.APPROVED.value


@pytest.mark.asyncio
async def test_reject_restores_previous_approved_answer(db_session):
    org = Organization(name="Reject Org", slug="reject-org")
    db_session.add(org)
    db_session.flush()
    from app.models.questionnaire import Question, Questionnaire, Answer
    from app.services.questionnaire.normalize import normalize_question

    questionnaire = Questionnaire(organization_id=org.id, name="Q")
    db_session.add(questionnaire)
    db_session.flush()
    question = Question(
        organization_id=org.id,
        questionnaire_id=questionnaire.id,
        external_id="Q-1",
        text="Test?",
        normalized_text=normalize_question("Test?"),
        sort_order=0,
    )
    db_session.add(question)
    db_session.flush()
    answer = Answer(
        organization_id=org.id,
        question_id=question.id,
        draft_text="New stale draft",
        approved_text="Old approved",
        status=AnswerStatus.NEEDS_REVIEW.value,
        regeneration_backup={
            "approved_text": "Old approved",
            "draft_text": "Old approved",
            "status": AnswerStatus.APPROVED.value,
        },
    )
    db_session.add(answer)
    db_session.flush()

    from uuid import uuid4

    AnsweringService(db_session).reject_answer(answer, uuid4())
    assert answer.approved_text == "Old approved"
    assert answer.status == AnswerStatus.APPROVED.value


def test_stale_answers_tenant_isolation(client: TestClient, db_session):
    org1 = Organization(name="O1", slug="o1-stale")
    org2 = Organization(name="O2", slug="o2-stale")
    user1 = User(email="iso@example.com", full_name="Iso", hashed_password=hash_password("x"))
    db_session.add_all([org1, org2, user1])
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org1.id, user_id=user1.id, role=Role.VIEWER.value)
    )
    from app.models.questionnaire import Question, Questionnaire, Answer
    from app.services.questionnaire.normalize import normalize_question

    qn = Questionnaire(organization_id=org2.id, name="X")
    db_session.add(qn)
    db_session.flush()
    q = Question(
        organization_id=org2.id,
        questionnaire_id=qn.id,
        external_id="X1",
        text="Secret?",
        normalized_text=normalize_question("Secret?"),
        sort_order=0,
    )
    db_session.add(q)
    db_session.flush()
    db_session.add(
        Answer(
            organization_id=org2.id,
            question_id=q.id,
            draft_text="secret",
            potentially_stale=True,
        )
    )
    db_session.commit()

    token = create_access_token(str(user1.id), {"organization_id": str(org1.id), "role": Role.VIEWER.value})
    resp = client.get("/api/v1/stale-answers", headers=_headers(token, str(org1.id)))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_viewer_cannot_revalidate(client: TestClient, db_session):
    org = Organization(name="RBAC", slug="rbac-stale")
    user = User(email="viewer@example.com", full_name="Viewer", hashed_password=hash_password("x"))
    db_session.add_all([org, user])
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.VIEWER.value)
    )
    from app.models.questionnaire import Question, Questionnaire, Answer
    from app.services.questionnaire.normalize import normalize_question

    qn = Questionnaire(organization_id=org.id, name="R")
    db_session.add(qn)
    db_session.flush()
    q = Question(
        organization_id=org.id,
        questionnaire_id=qn.id,
        external_id="R1",
        text="?",
        normalized_text=normalize_question("?"),
        sort_order=0,
    )
    db_session.add(q)
    db_session.flush()
    answer = Answer(organization_id=org.id, question_id=q.id, draft_text="d", potentially_stale=True)
    db_session.add(answer)
    db_session.commit()

    token = create_access_token(str(user.id), {"organization_id": str(org.id), "role": Role.VIEWER.value})
    resp = client.post(
        f"/api/v1/stale-answers/{answer.id}/revalidate",
        headers=_headers(token, str(org.id)),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_audit_events_recorded(db_session, demo_repo_path: str):
    from app.models.audit import AuditEvent

    org, project, question = await _seed_question_with_evidence(db_session, demo_repo_path)
    answer_service = AnsweringService(db_session)
    answer = await answer_service.generate_for_question(question=question)
    answer.potentially_stale = True
    db_session.flush()
    StalenessService(db_session).revalidate(organization_id=org.id, answer_id=answer.id, user_id=None)
    db_session.flush()
    actions = [
        row[0]
        for row in db_session.query(AuditEvent.action).filter(AuditEvent.organization_id == org.id).all()
    ]
    assert "stale_answer_revalidated" in actions


async def _seed_question_with_evidence(db_session, demo_repo_path: str):
    import uuid

    org = Organization(name="Staleness Org", slug=f"staleness-org-{uuid.uuid4().hex[:8]}")
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
        name="Security",
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
