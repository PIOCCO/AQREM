import re

_EVIDENCE_LINK = re.compile(r"\[([^\]]+)\]\(/evidence/[^)]+\)")


def sanitize_shared_messages(messages: list[dict]) -> list[dict]:
    """Read-only public view: do not expose deep links to evidence the viewer cannot open."""
    sanitized: list[dict] = []
    for message in messages:
        content = str(message.get("content") or "")
        if message.get("role") == "assistant":
            content = _EVIDENCE_LINK.sub(r"\1", content)
        sanitized.append({**message, "content": content})
    return sanitized
