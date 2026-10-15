"""User-facing chat message templates."""


def format_no_indexed_documents_message() -> str:
    return "No documents are indexed yet. Ask your admin to upload sources."


def format_no_relevant_information_message() -> str:
    return "I couldn't find relevant information in your documents."


def format_insufficient_evidence_message(*, project_name: str | None, sources_searched: int) -> str:
    scoped_to_project = bool(project_name and project_name.strip())
    label = project_name.strip() if scoped_to_project else "your organization"
    n = max(0, int(sources_searched))
    source_phrase = f"{n} source{'s' if n != 1 else ''} searched"
    tail = (
        "Try rephrasing, or add the document that covers it."
        if scoped_to_project
        else "Try rephrasing, or ask your admin to add the document that covers it."
    )
    return f"I couldn't find evidence for that in **{label}** ({source_phrase}). {tail}"


def format_empty_retrieval_message(
    *,
    org_chunk_count: int,
) -> str:
    if org_chunk_count <= 0:
        return format_no_indexed_documents_message()
    return format_no_relevant_information_message()
