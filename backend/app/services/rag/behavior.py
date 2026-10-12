"""Conceptual AI behavior: outcomes, conflicts, partial answers, action detection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.enums import AnswerOutcome

_ACTION_PATTERNS = re.compile(
    r"(?i)\b("
    r"approve this|reject this|upload the|replace the|create an evidence|"
    r"ask the .+ to upload|send a request to|delete the|archive the"
    r")\b",
)

_DOCUMENT_SEARCH_PATTERNS = re.compile(
    r"(?i)\b("
    r"penetration test report|business continuity plan|signed contract|"
    r"yesterday's uploaded|latest .+ report|send me the|show me the .+ document"
    r")\b",
)

_UNAUTHORIZED_INTENT = re.compile(
    r"(?i)\b("
    r"another customer|other customer|other tenant|different organization|"
    r"reveal the api key|show me the api key|api key|secret key|credentials for|"
    r"ignore (all )?(previous|prior) instructions"
    r")\b",
)

_VAGUE_QUESTION = re.compile(
    r"(?i)^(?:what about|tell me about|policy|security|help)\??$",
)


@dataclass
class EvidenceConflict:
    topic: str
    detail: str
    source_paths: list[str] = field(default_factory=list)


@dataclass
class BehaviorResult:
    outcome: AnswerOutcome
    missing_information: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    conflicts: list[EvidenceConflict] = field(default_factory=list)
    needs_review: bool = False
    employee_message_prefix: str = ""


def detect_action_request(question: str) -> bool:
    return bool(_ACTION_PATTERNS.search(question))


def looks_like_document_lookup(question: str) -> bool:
    return bool(_DOCUMENT_SEARCH_PATTERNS.search(question))


def detect_unauthorized_intent(question: str) -> bool:
    return bool(_UNAUTHORIZED_INTENT.search(question))


def needs_clarification(question: str) -> bool:
    q = question.strip()
    if len(q) < 15 and q.endswith("?"):
        return True
    return bool(_VAGUE_QUESTION.match(q))


def _evidence_blob(items: list) -> str:
    parts: list[str] = []
    for item in items:
        parts.append(getattr(item, "content", "") or "")
        parts.append(getattr(item, "file_path", "") or "")
        parts.append(getattr(item, "file_name", "") or "")
    return "\n".join(parts).lower()


def detect_conflicts(items: list) -> list[EvidenceConflict]:
    blob_by_path: dict[str, str] = {}
    for item in items:
        path = getattr(item, "file_path", None) or getattr(item, "file_name", None) or str(getattr(item, "id", ""))
        blob_by_path[path] = (blob_by_path.get(path, "") + " " + (getattr(item, "content", "") or "")).lower()

    combined = _evidence_blob(items)
    conflicts: list[EvidenceConflict] = []

    if "90 days" in combined and "180 days" in combined:
        paths = [p for p, b in blob_by_path.items() if "90 days" in b or "180 days" in b]
        conflicts.append(
            EvidenceConflict(
                topic="access review frequency",
                detail="Sources cite both 90-day and 180-day access review intervals.",
                source_paths=paths[:6],
            )
        )
    return conflicts


def _check_partial_multi_part(question: str, evidence: str) -> list[str]:
    """Return list of question aspects not supported by evidence text."""
    q = question.lower()
    missing: list[str] = []
    checks = [
        (["at rest", "rest"], ["aes", "at rest", "encrypt"]),
        (["in transit", "transit"], ["tls", "transit", "ssl"]),
        (["retention period", "retention"], ["retention"]),
        (["who approved", "approver"], ["approved", "approver", "signed by"]),
        (["next disaster recovery", "next dr"], ["next", "scheduled"]),
    ]
    for q_terms, ev_needles in checks:
        if any(t in q for t in q_terms):
            if not any(n in evidence for n in ev_needles):
                missing.append(q_terms[0])
    return missing


def classify_early_behavior(
    *,
    question: str,
    retrieval_error: str | None = None,
) -> BehaviorResult | None:
    """Outcomes that do not require an LLM call."""
    if detect_unauthorized_intent(question):
        return BehaviorResult(
            outcome=AnswerOutcome.ACCESS_DENIED,
            next_steps=[
                "Use your organization's official channels for credentials and cross-team data access.",
            ],
            employee_message_prefix=(
                "I cannot fulfill that request. Access is limited to your organization's authorized evidence. "
            ),
        )

    if needs_clarification(question):
        return BehaviorResult(
            outcome=AnswerOutcome.CLARIFICATION_REQUIRED,
            next_steps=[
                "Specify the policy, document, system, or timeframe you need (for example, data retention for customer logs).",
            ],
            employee_message_prefix="Your question is too broad to interpret reliably from indexed sources alone. ",
        )

    if detect_action_request(question):
        return BehaviorResult(
            outcome=AnswerOutcome.ACTION_NOT_SUPPORTED,
            needs_review=False,
            next_steps=[
                "Use the appropriate screen in AQREM (Review Queue, Sources, or Questionnaires) if you need to perform this action.",
            ],
            employee_message_prefix=(
                "I can help find and explain evidence, but I cannot perform that operation from chat. "
            ),
        )

    if retrieval_error:
        return BehaviorResult(
            outcome=AnswerOutcome.SOURCE_UNAVAILABLE,
            next_steps=["Retry later or check that sources are connected and indexed."],
            employee_message_prefix="Search could not be completed reliably. ",
        )
    return None


def classify_behavior(
    *,
    question: str,
    evidence_items: list,
    llm_sufficiency: str,
    retrieval_error: str | None = None,
) -> BehaviorResult:
    early = classify_early_behavior(question=question, retrieval_error=retrieval_error)
    if early:
        return early

    if not evidence_items:
        steps = [
            "Upload the document to a project source, or connect the repository where it is stored.",
            "Confirm you are scoped to the correct project in the sidebar.",
        ]
        prefix = (
            "I could not find matching content in your authorized, connected sources. "
            "This does not prove the item does not exist elsewhere in the company. "
        )
        if looks_like_document_lookup(question):
            prefix = (
                "I searched your indexed project sources and did not find that document or report. "
            )
        return BehaviorResult(
            outcome=AnswerOutcome.INSUFFICIENT_EVIDENCE,
            next_steps=steps,
            employee_message_prefix=prefix,
        )

    conflicts = detect_conflicts(evidence_items)
    if conflicts:
        return BehaviorResult(
            outcome=AnswerOutcome.CONFLICTING_EVIDENCE,
            conflicts=conflicts,
            needs_review=True,
            next_steps=[
                "Review both sources in the Review Queue or with your policy owner.",
                "Do not assume the newest file is authoritative unless your approval rules say so.",
            ],
            employee_message_prefix="Retrieved sources contain a material conflict. ",
        )

    evidence = _evidence_blob(evidence_items)
    missing_parts = _check_partial_multi_part(question, evidence)

    if llm_sufficiency == "insufficient":
        return BehaviorResult(
            outcome=AnswerOutcome.INSUFFICIENT_EVIDENCE,
            missing_information=missing_parts,
            next_steps=[
                "Upload or connect additional sources, or narrow the question to indexed material.",
            ],
            employee_message_prefix="Available evidence does not adequately support an answer. ",
        )

    if missing_parts:
        return BehaviorResult(
            outcome=AnswerOutcome.PARTIALLY_ANSWERED,
            missing_information=missing_parts,
            needs_review=True,
            next_steps=["Provide the missing policy or clarify which document should govern."],
            employee_message_prefix="",
        )

    return BehaviorResult(
        outcome=AnswerOutcome.ANSWERED,
        needs_review=llm_sufficiency != "sufficient",
    )


def compose_employee_answer(base_answer: str, behavior: BehaviorResult) -> str:
    parts: list[str] = []
    if behavior.employee_message_prefix:
        parts.append(behavior.employee_message_prefix.strip())
    if base_answer.strip():
        parts.append(base_answer.strip())

    if behavior.conflicts:
        parts.append("\n\n**Conflicting sources:**")
        for c in behavior.conflicts:
            paths = ", ".join(c.source_paths[:3]) or "see citations"
            parts.append(f"- {c.topic}: {c.detail} ({paths})")

    if behavior.missing_information:
        parts.append("\n\n**Not found in retrieved evidence:** " + ", ".join(behavior.missing_information))

    if behavior.next_steps:
        parts.append("\n\n**Suggested next steps:**")
        for step in behavior.next_steps:
            parts.append(f"- {step}")

    if behavior.needs_review and behavior.outcome not in {
        AnswerOutcome.ACTION_NOT_SUPPORTED,
        AnswerOutcome.INSUFFICIENT_EVIDENCE,
    }:
        parts.append("\n\n_This response should be reviewed before use in a formal questionnaire._")

    return "\n".join(parts).strip()
