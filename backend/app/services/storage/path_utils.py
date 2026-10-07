"""Safe blob paths and archive member names."""

from __future__ import annotations

import os
import re
from pathlib import Path, PurePosixPath

_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9._-]+$")


def safe_blob_filename(filename: str) -> str:
    """Basename only; reject path traversal in upload names."""
    name = (filename or "upload.bin").replace("\\", "/")
    if ".." in name or "\0" in name:
        raise ValueError("Invalid upload filename")
    base = PurePosixPath(name).name
    if not base or not _SAFE_FILENAME.match(base):
        raise ValueError("Invalid upload filename")
    return base


def resolve_under_root(root: Path, blob_path: str) -> Path:
    """Resolve blob_path under root; raise if it escapes."""
    root_resolved = root.resolve()
    full = (root / blob_path).resolve()
    if not str(full).startswith(str(root_resolved) + os.sep) and full != root_resolved:
        raise ValueError("Invalid blob path")
    return full


def safe_archive_member_path(name: str) -> str | None:
    normalized = name.replace("\\", "/")
    parts = [p for p in normalized.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        return None
    return "/".join(parts)
