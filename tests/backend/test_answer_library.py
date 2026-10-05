from pathlib import Path

import pytest

from app.models.answer_library import AnswerLibraryEntry
from app.models.enums import AnswerGenerationSource, EvidenceScope, SourceType, SyncJobStatus
from app.models.organization import Organization, User
from app.models.project import Project
from app.models.questionnaire import Question, Questionnaire
from app.models.source import Source, SourceSyncJob
from app.services.answering.service import AnsweringService
from app.services.ingestion.indexer import FilePayload, index_files
from app.services.library.validation import validate_library_evidence
from app.services.questionnaire.normalize import normalize_question


@pytest.mark.asyncio
async def test_approved_answer_creates_library_entry(db_session, demo_repo_path: str):
    org, project, question = await _seed_question_with_evidence(db_session, demo_repo_path)
    user = User(email="lib@example.com", full_name="Lib Tester", hashed_password="x")
    db_session.add(user)
    db_session.flush()

    service = AnsweringService(db_session)
    answer = await service.generate_for_question(question=question)
    await service.approve_answer(answer, user.id)
    db_session.flush()

    entry = (
        db_session.query(AnswerLibraryEntry)
        .filter(AnswerLibraryEntry.source_answer_id == answer.id)
        .first()
    )
    assert entry is not None
    assert entry.answer_text
    assert validate_library_evidence(db_session, entry).valid


@pytest.mark.asyncio
async def test_similar_question_reuses_library_entry(db_session, demo_repo_path: str):
    org, project, question = await _seed_question_with_evidence(db_session, demo_repo_path)
    answer_service = AnsweringService(db_session)
    first = await answer_service.generate_for_question(question=question)
    user = User(email="reuse@example.com", full_name="Reuse Tester", hashed_password="x")
    db_session.add(user)
    db_session.flush()

    await answer_service.approve_answer(first, user.id)
    db_session.flush()

    questionnaire = db_session.get(Questionnaire, question.questionnaire_id)
    assert questionnaire is not None
    similar = Question(
        organization_id=org.id,
        questionnaire_id=questionnaire.id,
        external_id="SEC-002",
        text="Do you encrypt customer data at rest?",  # exact match
        normalized_text=normalize_question("Do you encrypt customer data at rest?"),
        sort_order=1,
    )
    db_session.add(similar)
    db_session.flush()

    second = await answer_service.generate_for_question(question=similar)
    assert second.generation_source == AnswerGenerationSource.LIBRARY_REUSE.value
    assert second.library_entry_id is not None


@pytest.mark.asyncio
async def test_library_not_reused_when_evidence_changed(db_session, demo_repo_path: str):
    org, project, question = await _seed_question_with_evidence(db_session, demo_repo_path)
    answer_service = AnsweringService(db_session)
    first = await answer_service.generate_for_question(question=question)
    user = User(email="stale@example.com", full_name="Stale Tester", hashed_password="x")
    db_session.add(user)
    db_session.flush()

    await answer_service.approve_answer(first, user.id)
    db_session.flush()

    source = (
        db_session.query(Source)
        .filter(Source.organization_id == org.id, Source.project_id == project.id)
        .first()
    )
    assert source is not None
    job = SourceSyncJob(
        organization_id=org.id, source_id=source.id, status=SyncJobStatus.RUNNING.value
    )
    db_session.add(job)
    db_session.flush()

    mutated = FilePayload(
        relative_path="docs/architecture.md",
        data=b"# Architecture\n\nNo encryption guarantees are documented anymore.",
    )
    await index_files(db_session, source=source, job=job, files=[mutated])
    db_session.flush()

    questionnaire = db_session.get(Questionnaire, question.questionnaire_id)
    assert questionnaire is not None
    similar = Question(
        organization_id=org.id,
        questionnaire_id=questionnaire.id,
        external_id="SEC-003",
        text="Do you encrypt customer data at rest?",
        normalized_text=normalize_question("Do you encrypt customer data at rest?"),
        sort_order=2,
    )
    db_session.add(similar)
    db_session.flush()

    second = await answer_service.generate_for_question(question=similar)
    assert second.generation_source == AnswerGenerationSource.RETRIEVAL_LLM.value


async def _seed_question_with_evidence(db_session, demo_repo_path: str):
    import uuid

    org = Organization(name="Library Org", slug=f"library-org-{uuid.uuid4().hex[:8]}")
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
