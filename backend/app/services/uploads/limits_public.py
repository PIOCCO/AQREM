"""Public upload limit payloads (chat vs org-admin documents)."""

from __future__ import annotations

from app.core.config import get_settings


def chat_attachment_limits_payload() -> dict:
    s = get_settings()
    return {
        "max_bytes_per_file": s.chat_attachment_max_bytes,
        "max_files_per_message": s.chat_attachment_max_files,
        "max_total_bytes_per_message": s.chat_attachment_max_total_bytes,
        "max_pdf_pages": s.chat_attachment_max_pdf_pages,
        "max_text_chars": s.chat_attachment_max_text_chars,
        "uploads_per_hour": s.chat_attachment_uploads_per_hour,
        "allowed_extensions": sorted(s.chat_allowed_extensions_set),
        "helper_text": (
            "PDF, Markdown or text. Up to "
            f"{s.chat_attachment_max_files} files, {s.chat_attachment_max_mb} MB each, "
            f"{s.chat_attachment_max_pdf_pages} pages per PDF. Need more? Upload larger files in Documents."
        ),
    }


def org_document_limits_payload() -> dict:
    s = get_settings()
    return {
        "max_bytes_per_file": s.max_upload_bytes,
        "allowed_extensions": sorted(s.allowed_extensions_set),
        "helper_text": f"PDF, Markdown, plain text, and .tar.gz archives. Max {s.max_upload_bytes // (1024 * 1024)} MB per file.",
    }
