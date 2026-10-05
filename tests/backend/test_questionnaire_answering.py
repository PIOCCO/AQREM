import asyncio
from pathlib import Path

import pytest

from app.models.enums import EvidenceScope, SourceType, SyncJobStatus
from app.models.organization import Organization
from app.models.project import Project
from app.models.questionnaire import AnswerEvidenceLink, Question, Questionnaire
from app.models.source import Source, SourceSyncJob
from app.services.answering.service import AnsweringService
from app.services.ingestion.indexer import FilePayload, index_files
from app.services.questionnaire.extract import extract_from_csv
from app.services.questionnaire.normalize import normalize_question


@pytest.mark.asyncio
async def test_extract_csv_questions():
    csv_data = b"question_id,section,question\nSEC-001,Security,Do you encrypt customer data at rest?\n"
    rows = extract_from_csv(csv_data)
    assert len(rows) == 1
    assert rows[0].external_id == "SEC-001"


@pytest.mark.asyncio
async def test_generate_answer_with_evidence_citations(db_session, demo_repo_path: str):
    org = Organization(name="Acme", slug="acme-q")
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
        section="Security",
        text="Do you encrypt customer data at rest?",
        normalized_text=normalize_question("Do you encrypt customer data at rest?"),
        sort_order=0,
    )
    db_session.add(question)
    db_session.flush()

    answer = await AnsweringService(db_session).generate_for_question(question=question)
    db_session.flush()

    assert answer.evidence_sufficiency == "sufficient"
    assert answer.draft_text
    link_count = (
        db_session.query(AnswerEvidenceLink).filter(AnswerEvidenceLink.answer_id == answer.id).count()
    )
    assert link_count >= 1


@pytest.mark.asyncio
async def test_insufficient_evidence_without_sources(db_session):
    org = Organization(name="Lonely Org", slug="lonely")
    db_session.add(org)
    db_session.flush()
    questionnaire = Questionnaire(organization_id=org.id, name="Empty")
    db_session.add(questionnaire)
    db_session.flush()
    question = Question(
        organization_id=org.id,
        questionnaire_id=questionnaire.id,
        external_id="Q-001",
        text="Describe your quantum computer policy?",
        normalized_text=normalize_question("Describe your quantum computer policy?"),
        sort_order=0,
    )
    db_session.add(question)
    db_session.flush()

    answer = await AnsweringService(db_session).generate_for_question(question=question)
    assert answer.evidence_sufficiency == "insufficient"
    assert "Insufficient evidence" in answer.draft_text
