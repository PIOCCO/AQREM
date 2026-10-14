"""Server-side validation for chat composer attachments."""

from __future__ import annotations

import io
from pypdf import PdfReader

from app.core.config import Settings
from app.services.ingestion.parsers import parse_bytes
from app.services.uploads.file_signature import detect_upload_kind


class ChatValidationError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 400) -> None:
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(message)


def validate_chat_filename(name: str, settings: Settings) -> str:
    lower = name.lower().strip()
    if lower.endswith(".tar.gz") or lower.endswith(".zip"):
        raise ChatValidationError(
            code="ARCHIVE_NOT_IN_CHAT",
            message="Archive files cannot be attached in chat. Use the Documents page for .tar.gz uploads.",
            http_status=415,
        )
    ext = ".md" if lower.endswith(".md") else ".txt" if lower.endswith(".txt") else ".pdf" if lower.endswith(".pdf") else None
    if ext is None or ext not in settings.chat_allowed_extensions_set:
        allowed = ", ".join(sorted(settings.chat_allowed_extensions_set))
        raise ChatValidationError(
            code="TYPE_NOT_ALLOWED",
            message=f"This file type is not allowed in chat. Allowed: {allowed}.",
            http_status=415,
        )
    return ext


def validate_chat_file_content(*, safe_name: str, data: bytes, settings: Settings) -> None:
    if not data:
        raise ChatValidationError(code="EMPTY_FILE", message="This file is empty.", http_status=422)
    if len(data) > settings.chat_attachment_max_bytes:
        raise ChatValidationError(
            code="FILE_TOO_LARGE",
            message=f"This file is too large. The chat limit is {settings.chat_attachment_max_mb} MB per file.",
            http_status=413,
        )
    kind = detect_upload_kind(data, filename=safe_name)
    if kind == "empty":
        raise ChatValidationError(code="EMPTY_FILE", message="This file is empty.", http_status=422)
    if kind is None:
        raise ChatValidationError(
            code="INVALID_SIGNATURE",
            message="This file does not match its type. Upload a valid PDF, Markdown, or text file.",
            http_status=415,
        )
    if kind == "pdf":
        reader = PdfReader(io.BytesIO(data))
        page_count = len(reader.pages)
        if page_count > settings.chat_attachment_max_pdf_pages:
            raise ChatValidationError(
                code="PDF_TOO_MANY_PAGES",
                message=(
                    f"This PDF has {page_count} pages. The chat limit is {settings.chat_attachment_max_pdf_pages}. "
                    "Upload it in Documents instead."
                ),
                http_status=422,
            )
        text_sample = "\n".join((page.extract_text() or "") for page in reader.pages[: min(3, page_count)])
        if not text_sample.strip():
            raise ChatValidationError(
                code="PDF_NO_TEXT",
                message="This PDF has no extractable text (it may be scanned). Upload it in Documents or use a text-based PDF.",
                http_status=422,
            )
    text, _ctype = parse_bytes(safe_name, data)
    if len(text) > settings.chat_attachment_max_text_chars:
        raise ChatValidationError(
            code="TEXT_TOO_LONG",
            message=(
                f"This file has too much text for chat ({len(text):,} characters). "
                f"The limit is {settings.chat_attachment_max_text_chars:,}. Upload it in Documents instead."
            ),
            http_status=422,
        )
