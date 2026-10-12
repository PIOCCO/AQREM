"""User-facing chat message templates."""


def format_insufficient_evidence_message(*, project_name: str | None, sources_searched: int) -> str:
    label = project_name.strip() if project_name and project_name.strip() else "this project"
    n = max(0, int(sources_searched))
    source_phrase = f"{n} source{'s' if n != 1 else ''} searched"
    return (
        f"I couldn't find evidence for that in **{label}** ({source_phrase}). "
        "Try rephrasing, or add the document that covers it."
    )
