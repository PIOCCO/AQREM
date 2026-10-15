"""Keyword term extraction for short person / name lookups."""

from __future__ import annotations

import re

_WHO_IS = re.compile(r"(?i)^who(?:'s|\s+is)\s+(.+?)[\s?.!]*$")
_WHAT_IS = re.compile(r"(?i)^what(?:'s|\s+is)\s+(.+?)[\s?.!]*$")
_TELL_ME = re.compile(r"(?i)^tell me about\s+(.+?)[\s?.!]*$")
_EXPERIENCE = re.compile(r"(?i)^what experience(?: has| did)?\s+(.+?)(?:\s+done)?[\s?.!]*$")


def extract_keyword_terms(query: str) -> list[str]:
    q = query.strip()
    if not q:
        return []
    for pattern in (_WHO_IS, _WHAT_IS, _TELL_ME, _EXPERIENCE):
        m = pattern.match(q)
        if m:
            q = m.group(1).strip()
            break
    q = re.sub(r"[^\w\s-]", " ", q)
    terms = [t for t in q.split() if len(t) >= 2]
    # Drop common question words that hurt ILIKE matching.
    stop = {"who", "what", "the", "has", "have", "done", "about", "experience", "he", "she", "they"}
    filtered = [t for t in terms if t.lower() not in stop]
    return (filtered or terms)[:8]
