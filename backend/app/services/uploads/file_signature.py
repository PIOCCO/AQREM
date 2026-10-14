"""Magic-byte checks for chat uploads (do not trust client MIME)."""

from __future__ import annotations


def detect_upload_kind(data: bytes, *, filename: str) -> str | None:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        if data[:5] == b"%PDF-":
            return "pdf"
        return None
    if lower.endswith(".md") or lower.endswith(".txt"):
        if not data:
            return "empty"
        try:
            data[:4096].decode("utf-8")
        except UnicodeDecodeError:
            return None
        return "text"
    return None
