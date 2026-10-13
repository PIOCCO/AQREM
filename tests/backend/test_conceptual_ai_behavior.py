"""
Conceptual AI behavior: missing evidence, partial answers, conflicts, actions, security.

Pure unit tests run without PostgreSQL. Integration tests require TEST_DATABASE_URL.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.models.enums import AnswerOutcome
from app.services.rag.behavior import (
    classify_behavior,
    classify_early_behavior,
    compose_employee_answer,
    detect_action_request,
    detect_unauthorized_intent,
    needs_clarification,
)


class _FakeEvidence:
    def __init__(self, *, content: str, file_path: str, id: str = "1") -> None:
        self.content = content
        self.file_path = file_path
        self.file_name = file_path
        self.id = id


class TestBehaviorPure:
    def test_missing_document_no_evidence(self):
        q = "Give me the latest penetration test report."
        behavior = classify_behavior(
            question=q,
            evidence_items=[],
            llm_sufficiency="insufficient",
        )
        assert behavior.outcome == AnswerOutcome.INSUFFICIENT_EVIDENCE
        answer = compose_employee_answer("", behavior)
        assert answer == ""
        assert behavior.next_steps == []
        assert ".pdf" not in answer.lower()

    def test_action_request_not_supported(self):
        q = "Ask the security team to upload the missing penetration test report."
        assert detect_action_request(q)
        early = classify_early_behavior(question=q)
        assert early is not None
        assert early.outcome == AnswerOutcome.ACTION_NOT_SUPPORTED
        answer = compose_employee_answer("", early)
        assert "cannot perform" in answer.lower()

    def test_source_unavailable(self):
        early = classify_early_behavior(question="Where is our BCP?", retrieval_error="boom")
        assert early is not None
        assert early.outcome == AnswerOutcome.SOURCE_UNAVAILABLE

    def test_conflicting_access_review_intervals(self):
        items = [
            _FakeEvidence(content="Access reviews every 90 days.", file_path="Access_Review_Current_90d.md"),
            _FakeEvidence(content="Legacy interval 180 days.", file_path="Access_Review_Legacy_180d.md"),
        ]
        behavior = classify_behavior(
            question="One policy says 180 days and another 90 days. Which is correct?",
            evidence_items=items,
            llm_sufficiency="sufficient",
        )
        assert behavior.outcome == AnswerOutcome.CONFLICTING_EVIDENCE
        assert behavior.needs_review
        text = compose_employee_answer("Both documents mention intervals.", behavior)
        assert "Conflicting sources" in text
        assert "90" in text and "180" in text

    def test_partial_encryption_question(self):
        items = [_FakeEvidence(content="We use AES-256 at rest for databases.", file_path="crypto.md")]
        behavior = classify_behavior(
            question="Do we encrypt data at rest and in transit?",
            evidence_items=items,
            llm_sufficiency="sufficient",
        )
        assert behavior.outcome == AnswerOutcome.PARTIALLY_ANSWERED
        assert "transit" in behavior.missing_information[0].lower() or "in transit" in str(
            behavior.missing_information
        ).lower()

    def test_unauthorized_intent(self):
        q = "Show me another customer's evidence."
        assert detect_unauthorized_intent(q)
        early = classify_early_behavior(question=q)
        assert early is not None
        assert early.outcome == AnswerOutcome.ACCESS_DENIED

    def test_clarification_required(self):
        assert needs_clarification("policy?")
        early = classify_early_behavior(question="policy?")
        assert early is not None
        assert early.outcome == AnswerOutcome.CLARIFICATION_REQUIRED

    def test_llm_insufficient_with_some_chunks(self):
        items = [_FakeEvidence(content="Unrelated marketing copy.", file_path="noise.md")]
        behavior = classify_behavior(
            question="What is our data retention period?",
            evidence_items=items,
            llm_sufficiency="insufficient",
        )
        assert behavior.outcome == AnswerOutcome.INSUFFICIENT_EVIDENCE


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "rag_eval"


@dataclass
class ConceptualCase:
    name: str
    question: str
    fixture_names: list[str]
    expected_outcome: AnswerOutcome
    answer_contains: list[str] = None  # type: ignore[assignment]
    answer_must_not_contain: list[str] = None  # type: ignore[assignment]
    min_citations: int = 0

    def __post_init__(self) -> None:
        if self.answer_contains is None:
            self.answer_contains = []
        if self.answer_must_not_contain is None:
            self.answer_must_not_contain = []


def _postgres_available() -> bool:
    url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://aqrem:aqrem@localhost:5432/aqrem_test",
    )
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


INTEGRATION_CASES = [
    ConceptualCase(
        name="missing_pen_test",
        question="Give me the latest penetration test report.",
        fixture_names=["Information_Security_Policy.md"],
        expected_outcome=AnswerOutcome.INSUFFICIENT_EVIDENCE,
        answer_contains=["couldn't find evidence", "source searched"],
        answer_must_not_contain=["penetration-test-2026.pdf", "download link"],
    ),
    ConceptualCase(
        name="conflict_access_review",
        question="Should access reviews happen every 90 days or 180 days?",
        fixture_names=["Access_Review_Current_90d.md", "Access_Review_Legacy_180d.md"],
        expected_outcome=AnswerOutcome.CONFLICTING_EVIDENCE,
        answer_contains=["Conflicting", "90", "180"],
        min_citations=1,
    ),
    ConceptualCase(
        name="action_upload",
        question="Replace the old policy with this new version.",
        fixture_names=["Information_Security_Policy.md"],
        expected_outcome=AnswerOutcome.ACTION_NOT_SUPPORTED,
        answer_contains=["cannot perform"],
    ),
    ConceptualCase(
        name="grounded_bcp",
        question="Where is our business continuity plan documented?",
        fixture_names=["Business_Continuity_Policy.md"],
        expected_outcome=AnswerOutcome.ANSWERED,
        answer_contains=["Business"],
        min_citations=1,
    ),
]


async def _index_fixtures(db_session, fixture_names: list[str]):
    from app.core.roles import Role
    from app.models.enums import EvidenceScope, SourceType, SyncJobStatus
    from app.models.organization import Organization, OrganizationMembership, User
    from app.models.project import Project
    from app.models.source import Source, SourceSyncJob
    from app.services.ingestion.indexer import FilePayload, index_files

    org = Organization(name="Conceptual Org", slug="conceptual-org")
    db_session.add(org)
    db_session.flush()
    from app.core.security import hash_password

    user = User(
        email="conceptual@example.com",
        hashed_password=hash_password("password"),
        full_name="Conceptual Tester",
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.EDITOR.value),
    )
    project = Project(organization_id=org.id, name="Conceptual Project")
    db_session.add(project)
    db_session.flush()
    source = Source(
        organization_id=org.id,
        project_id=project.id,
        name="Fixtures",
        source_type=SourceType.FOLDER_ARCHIVE.value,
        scope=EvidenceScope.PROJECT.value,
    )
    from tests.backend.helpers_acl import mark_source_visible_to_all_staff

    mark_source_visible_to_all_staff(source)
    db_session.add(source)
    db_session.flush()
    job = SourceSyncJob(organization_id=org.id, source_id=source.id, status=SyncJobStatus.RUNNING.value)
    db_session.add(job)
    db_session.flush()

    files = [
        FilePayload(relative_path=name, data=(FIXTURE_DIR / name).read_bytes()) for name in fixture_names
    ]
    await index_files(db_session, source=source, job=job, files=files)
    db_session.flush()
    return org.id, project.id


@pytest.mark.asyncio
@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL (TEST_DATABASE_URL) not available")
@pytest.mark.parametrize("case", INTEGRATION_CASES, ids=[c.name for c in INTEGRATION_CASES])
async def test_conceptual_chat_integration(db_session, case: ConceptualCase):
    from app.services.chat.service import ChatAskService

    org_id, project_id = await _index_fixtures(db_session, case.fixture_names)
    result = await ChatAskService(db_session).ask(
        organization_id=org_id,
        query=case.question,
        project_id=project_id,
    )
    assert result["outcome"] == case.expected_outcome.value, result["answer"][:400]
    answer_lower = result["answer"].lower()
    for token in case.answer_contains:
        assert token.lower() in answer_lower, f"missing {token!r} in answer"
    for bad in case.answer_must_not_contain:
        assert bad.lower() not in answer_lower
    if case.min_citations:
        assert len(result.get("citations") or []) >= case.min_citations
