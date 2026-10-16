"""Safe blob paths and archive member names."""

from __future__ import annotations

import os
import re
from pathlib import Path, PurePosixPath

_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9._-]+$")


def safe_blob_filename(filename: str) -> str:
    """Basename only; reject path traversal; normalize spaces and unsafe characters."""
    name = (filename or "upload.bin").replace("\\", "/")
    if ".." in name or "\0" in name:
        raise ValueError("Invalid upload filename")
    base = PurePosixPath(name).name
    if not base or base in (".", ".."):
        raise ValueError("Invalid upload filename")
    if _SAFE_FILENAME.match(base):
        return base
    path = PurePosixPath(base)
    suffix = "".join(path.suffixes)
    stem = path.name[: -len(suffix)] if suffix else path.name
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    safe_suffix = re.sub(r"[^A-Za-z0-9._-]+", "", suffix)
    if not safe_stem:
        safe_stem = "upload"
    sanitized = f"{safe_stem}{safe_suffix}"
    if not _SAFE_FILENAME.match(sanitized):
        sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._-") or "upload.bin"
    if not sanitized or sanitized in (".", ".."):
        raise ValueError("Invalid upload filename")
    return sanitized


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


def org_blob_prefix(organization_id) -> str:
    """Every tenant object lives under '<organization_id>/' in the container."""
    return f"{organization_id}/"


def org_blob_path(organization_id, *parts: str) -> str:
    clean = []
    for part in parts:
        seg = str(part).strip("/")
        if not seg or ".." in seg.split("/") or "\0" in seg:
            raise ValueError("Invalid blob path segment")
        clean.append(seg)
    return org_blob_prefix(organization_id) + "/".join(clean)


def assert_blob_in_org(blob_path: str, organization_id) -> str:
    """Raise ValueError unless blob_path is inside the organization's prefix."""
    if not isinstance(blob_path, str) or "\0" in blob_path or ".." in blob_path.split("/"):
        raise ValueError("invalid blob path")
    if not blob_path.startswith(org_blob_prefix(organization_id)):
        raise ValueError("blob path outside organization scope")
    return blob_path
