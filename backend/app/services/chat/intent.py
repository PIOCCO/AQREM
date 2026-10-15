"""Lightweight chat intent routing before retrieval."""

from __future__ import annotations

import re

_GREETING = re.compile(
    r"(?i)^\s*(?:hi|hello|hey|hiya|howdy|good\s+(?:morning|afternoon|evening)|"
    r"what(?:'s|\s+is)\s+up|sup|yo)[\s!.?]*$"
)
_THANKS = re.compile(
    r"(?i)^\s*(?:thanks|thank\s+you|thx|ty|much\s+appreciated|appreciate\s+it)[\s!.?]*$"
)
_HELP = re.compile(
    r"(?i)^\s*(?:help(?:\s+me)?|what\s+can\s+you\s+do|how\s+does\s+this\s+work|"
    r"what\s+do\s+you\s+do|how\s+can\s+you\s+help)[\s?.!]*$"
)

STARTER_PROMPTS = (
    "Complete a questionnaire",
    "Find evidence for a control",
    "Check an answer against sources",
    "Summarize a policy",
)


def classify_chat_intent(query: str) -> str | None:
    """Return greeting, thanks, help, or None for a real question/task."""
    q = query.strip()
    if not q:
        return None
    if _GREETING.match(q):
        return "greeting"
    if _THANKS.match(q):
        return "thanks"
    if _HELP.match(q):
        return "help"
    if len(q) <= 12 and q.lower() in {"hi", "hey", "hello", "help"}:
        return "greeting" if q.lower() != "help" else "help"
    return None


def build_conversational_answer(intent: str) -> str:
    starters = "\n".join(f"- {s}" for s in STARTER_PROMPTS[:3])
    if intent == "greeting":
        return (
            "Hello! I'm here to help you find answers in your company documents and work through questionnaires.\n\n"
            f"**Try one of these:**\n{starters}"
        )
    if intent == "thanks":
        return (
            "You're welcome. If you have another question about your policies or evidence, ask anytime.\n\n"
            f"**Try one of these:**\n{starters}"
        )
    return (
        "I search your organization's indexed documents, cite evidence, and help with questionnaires and review workflows.\n\n"
        f"**Try one of these:**\n{starters}"
    )
