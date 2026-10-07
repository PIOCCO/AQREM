"""Third-pass security fixes: config injection, upload paths, production guards."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.sources.config_safety import sanitize_source_config_for_storage
from app.services.storage.path_utils import resolve_under_root, safe_archive_member_path, safe_blob_filename


def test_create_source_config_strips_inline_tokens():
    raw = {"github_token": "ghp_evil", "demo_path": "/etc", "repo": "ok"}
    safe = sanitize_source_config_for_storage(raw)
    assert "github_token" not in safe
    assert "demo_path" not in safe
    assert safe.get("repo") == "ok"


def test_safe_blob_filename_rejects_traversal():
    assert safe_blob_filename("report.pdf") == "report.pdf"
    with pytest.raises(ValueError):
        safe_blob_filename("../../etc/passwd")
    with pytest.raises(ValueError):
        safe_blob_filename("..")


def test_resolve_under_root_blocks_escape(tmp_path):
    root = tmp_path / "uploads"
    root.mkdir()
    inner = resolve_under_root(root, "org/source/file.txt")
    inner.parent.mkdir(parents=True, exist_ok=True)
    inner.write_text("x")
    with pytest.raises(ValueError):
        resolve_under_root(root, "../outside.txt")


def test_safe_archive_member_path():
    assert safe_archive_member_path("docs/readme.md") == "docs/readme.md"
    assert safe_archive_member_path("../../etc/passwd") is None


def test_production_rejects_weak_secret_key():
    with pytest.raises(ValidationError):
        Settings(app_env="production", secret_key="change-me-in-production")
