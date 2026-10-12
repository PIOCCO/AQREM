"""Questionnaire answering uses the same grounded RAG pipeline as chat."""

import pytest

from app.models.organization import Organization
from app.models.project import Project
from app.models.questionnaire import Question, Questionnaire
from app.services.answering.service import AnsweringService
from app.services.chat.service import ChatAskService
from app.services.questionnaire.normalize import normalize_question


@pytest.mark.asyncio
async def test_questionnaire_and_chat_share_insufficient_outcome(db_session):
    org = Organization(name="Parity Org", slug="parity-org", license_limit=5)
    db_session.add(org)
    db_session.flush()
    project = Project(organization_id=org.id, name="Policies")
    db_session.add(project)
    db_session.flush()

    question_text = "Where is the signed penetration test report from yesterday?"
    questionnaire = Questionnaire(organization_id=org.id, project_id=project.id, name="Q")
    db_session.add(questionnaire)
    db_session.flush()
    question = Question(
        organization_id=org.id,
        questionnaire_id=questionnaire.id,
        external_id="PEN-1",
        text=question_text,
        normalized_text=normalize_question(question_text),
        sort_order=0,
    )
    db_session.add(question)
    db_session.flush()

    chat = await ChatAskService(db_session).ask(
        organization_id=org.id,
        query=question_text,
        project_id=project.id,
    )
    answer = await AnsweringService(db_session).generate_for_question(question=question)
    db_session.flush()

    assert chat["evidence_sufficiency"] == "insufficient"
    assert answer.evidence_sufficiency == "insufficient"
    assert chat["outcome"] == answer.evidence_sufficiency or chat["outcome"] in {
        "insufficient_evidence",
        "source_unavailable",
    }
