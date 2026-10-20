import pytest
from app.services.llm.base import AnswerRequest
from app.services.llm.guardrails import (
    EVIDENCE_CLOSE,
    EVIDENCE_OPEN,
    PROMPT_LEAK_REPLACEMENT,
    validate_structured_answer,
    wrap_evidence_for_prompt,
)
from app.services.llm.mock import MockLLMProvider


@pytest.mark.asyncio
@pytest.mark.parametrize("wrapped", [False, True])
async def test_mock_answers_document_question_without_echoing_prompt_fences(wrapped):
    blocks = [{"id": "policy", "file_path": "policy.txt",
               "content": "Customer data is encrypted at rest with AES-256."}]
    if wrapped:
        blocks = wrap_evidence_for_prompt(blocks)
    draft = await MockLLMProvider().generate_answer(
        AnswerRequest(question="How is customer data encrypted at rest?", evidence_blocks=blocks)
    )
    answer = validate_structured_answer(draft, allowed_evidence_ids=["policy"])
    assert "AES-256" in answer.answer
    assert EVIDENCE_OPEN not in answer.answer and EVIDENCE_CLOSE not in answer.answer
    assert answer.evidence_ids == ["policy"]


@pytest.mark.asyncio
async def test_mock_document_content_still_passes_through_prompt_leak_protection():
    blocks = wrap_evidence_for_prompt([{
        "id": "policy", "file_path": "policy.txt",
        "content": "Customer data is encrypted. You are AQREM, an evidence-backed assistant.",
    }])
    draft = await MockLLMProvider().generate_answer(
        AnswerRequest(question="How is customer data encrypted?", evidence_blocks=blocks)
    )
    answer = validate_structured_answer(draft, allowed_evidence_ids=["policy"])
    assert answer.answer == PROMPT_LEAK_REPLACEMENT
