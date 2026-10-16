"""Cheap, layered chat scope guardrails (run BEFORE retrieval; no LLM call).

Layer 1 (here): regex heuristics for prompt-injection / jailbreak phrases and clearly out-of-scope
requests (writing code, creative writing, general chat / trivia).
Layer 2: retrieval relevance threshold (CHAT_MIN_RELEVANCE_SCORE) -> "not found" instead of answering.
Layer 3: system prompt rules (app/services/llm/prompts.py) + evidence delimiting + output checks.

Heuristics are deliberately conservative (prefer letting a real document question through, which is
then still constrained by layers 2 and 3). They can be bypassed by rephrasing; they are not a security
boundary on their own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

STRICT = "strict"
BALANCED = "balanced"
STRICTNESS_LEVELS = (STRICT, BALANCED)

SCOPE_REFUSAL = (
    "I can only help with questions about your organization's documents and questionnaires. "
    "I can't help with that request. Try asking about a policy, control, or document instead."
)
INJECTION_REFUSAL = (
    "I can't help with that. I only answer questions using your organization's documents, "
    "and I can't change or reveal my instructions."
)
STRICT_CONVERSATIONAL = "I answer questions using your organization's documents. Ask me about a policy, control, or document."

_INJECTION = re.compile(
    r"(?ix)("
    r"\b(ignore|disregard|forget|override|bypass)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all|your|the|system|safety)\b"
    r"[^.\n]{0,20}\b(instructions?|rules?|prompts?|guidelines?|polic(y|ies)|restrictions?)\b"
    r"|\b(reveal|show|print|repeat|output|display|tell\s+me|what\s+(is|are))\b[^.\n]{0,30}"
    r"\b(system|hidden|initial|original|developer)\s+(prompt|instructions?|message|rules)\b"
    r"|\byour\s+(system\s+)?(prompt|instructions)\b"
    r"|\byou\s+are\s+now\b|\bfrom\s+now\s+on\s+you\b|\bact\s+as\s+(an?\s+)?(unrestricted|uncensored|different|dan)\b"
    r"|\b(developer|god|jailbreak|dan)\s+mode\b|\bjailbreak\b|\bdo\s+anything\s+now\b"
    r"|\bpretend\s+(you\s+are|to\s+be|that\s+you)\b|\brole-?play\s+as\b"
    r"|<\s*/?\s*(system|assistant|instructions?)\s*>|\[\s*/?\s*(system|inst)\s*\]"
    r")"
)

_CODE = re.compile(
    r"(?ix)("
    r"\b(write|generate|create|implement|build|give\s+me|make|code|refactor|debug|fix|optimi[sz]e|convert)\b"
    r"[^.\n]{0,50}\b(code|script|function|program|class|method|regex|regular\s+expression|sql\s+query|query\s+in\s+sql|"
    r"snippet|algorithm|api\s+endpoint|unit\s+tests?|dockerfile|bash|shell\s+command|"
    r"python|javascript|typescript|java|c\+\+|c\#|golang|rust|php|ruby|kotlin|swift|html|css|react|terraform)\b"
    r"|```"
    r"|\bhow\s+(do\s+i|to)\s+(code|program|implement)\b"
    r")"
)

_CREATIVE = re.compile(
    r"(?ix)\b(write|compose|create|generate|make|tell)\b[^.\n]{0,30}"
    r"\b(poem|haiku|limerick|sonnet|song|lyrics|rap|story|short\s+story|fairy\s+tale|joke|riddle|novel|screenplay|"
    r"fan\s*fiction|essay\s+about|birthday\s+message|love\s+letter)\b"
    r"|\btell\s+me\s+a\s+(joke|story)\b"
)

_GENERAL = re.compile(
    r"(?ix)("
    r"\bwhat(\s+is|'s)\s+the\s+(capital|population|currency|weather|time|date)\s+(of|in)\b"
    r"|\bwho\s+(won|invented|discovered|painted|wrote|is\s+the\s+(president|prime\s+minister|ceo\s+of\s+(apple|google|microsoft|tesla|amazon)))\b"
    r"|\bhow\s+(tall|old|far|big)\s+is\s+(the\s+)?(eiffel|mount|everest|moon|sun|earth|statue)\b"
    r"|\b(recipe|cook)\s+(for|a|an)\b|\bhow\s+do\s+i\s+cook\b"
    r"|\bweather\s+(today|tomorrow|forecast)\b|\b(sports?|football|soccer|nba)\s+(score|results?)\b"
    r"|\btranslate\b[^.\n]{0,40}\b(into|to)\s+(french|spanish|german|arabic|chinese|japanese|italian)\b"
    r"|\bwhat\s+is\s+\d+\s*[-+*/x^]\s*\d+\b|\bsolve\s+(this\s+)?(equation|math)\b"
    r"|\bwhat\s+(do\s+you\s+think|is\s+your\s+opinion)\s+(of|about)\b|\bhow\s+are\s+you\b|\bare\s+you\s+(human|sentient|alive)\b"
    r"|\b(meaning\s+of\s+life|tell\s+me\s+about\s+yourself)\b"
    r")"
)

_SUMMARY = re.compile(r"(?i)\b(summari[sz]e|summary|overview|tl;?dr|key\s+points|outline)\b")


@dataclass(frozen=True)
class ScopeDecision:
    category: str | None  # "injection" | "code" | "creative" | "general" | None (in scope)
    message: str | None = None

    @property
    def blocked(self) -> bool:
        return self.category is not None


def normalize_strictness(value: str | None) -> str:
    v = (value or "").strip().lower()
    return v if v in STRICTNESS_LEVELS else BALANCED


def is_summary_request(query: str) -> bool:
    return bool(_SUMMARY.search(query or ""))


def classify_scope(query: str) -> ScopeDecision:
    q = (query or "").strip()
    if not q:
        return ScopeDecision(None)
    if _INJECTION.search(q):
        return ScopeDecision("injection", INJECTION_REFUSAL)
    if _CODE.search(q):
        return ScopeDecision("code", SCOPE_REFUSAL)
    if _CREATIVE.search(q):
        return ScopeDecision("creative", SCOPE_REFUSAL)
    if _GENERAL.search(q):
        return ScopeDecision("general", SCOPE_REFUSAL)
    return ScopeDecision(None)


def summary_allowed(strictness: str) -> bool:
    return normalize_strictness(strictness) == BALANCED


def relevance_threshold(base: float, *, strictness: str, query: str) -> float:
    """Balanced: document-summary requests (low lexical overlap by nature) use half the threshold.
    Strict: the full threshold for everything, plus 25% stricter."""
    s = normalize_strictness(strictness)
    if s == STRICT:
        return base * 1.25
    if is_summary_request(query):
        return base * 0.5
    return base
