"""Chat intent routing before retrieval."""

from app.services.chat.intent import classify_chat_intent, build_conversational_answer
from app.services.chat.messages import (
    format_empty_retrieval_message,
    format_insufficient_evidence_message,
    format_no_indexed_documents_message,
    format_no_relevant_information_message,
)


def test_greeting_intent():
    assert classify_chat_intent("Hello!") == "greeting"
    assert classify_chat_intent("hey") == "greeting"


def test_thanks_intent():
    assert classify_chat_intent("Thank you!") == "thanks"


def test_help_intent():
    assert classify_chat_intent("What can you do?") == "help"


def test_real_question_not_intent():
    assert classify_chat_intent("What is our data retention policy for customer logs?") is None


def test_conversational_answer_includes_starters():
    text = build_conversational_answer("greeting")
    assert "questionnaire" in text.lower()


def test_insufficient_evidence_message_template():
    msg = format_insufficient_evidence_message(project_name="Acme GRC", sources_searched=3)
    assert "Acme GRC" in msg
    assert "3 sources searched" in msg
    assert "authorized" not in msg.lower()


def test_insufficient_evidence_message_org_wide():
    msg = format_insufficient_evidence_message(project_name=None, sources_searched=2)
    assert "your organization" in msg
    assert "2 sources searched" in msg


def test_no_indexed_documents_message():
    msg = format_no_indexed_documents_message()
    assert "indexed" in msg.lower()
    assert "admin" in msg.lower()


def test_empty_retrieval_message_uses_chunk_count():
    assert "indexed" in format_empty_retrieval_message(org_chunk_count=0).lower()
    assert format_empty_retrieval_message(org_chunk_count=3) == format_no_relevant_information_message()
