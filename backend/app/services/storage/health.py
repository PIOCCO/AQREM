"""Verify blob storage is writable before accepting uploads."""

from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings


class StorageUnavailable(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def assert_upload_storage_ready() -> None:
    settings = get_settings()
    if settings.azure_storage_connection_string:
        return
    root = Path(settings.local_upload_dir)
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".aqrem_write_probe"
        probe.write_bytes(b"ok")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        raise StorageUnavailable(
            f"File storage is not writable at {root}. Set LOCAL_UPLOAD_DIR to a writable directory "
            f"(for example /tmp/aqrem/uploads). ({exc.strerror or exc})"
        ) from exc
    except Exception as exc:
        raise StorageUnavailable(
            "File storage is not available. Check LOCAL_UPLOAD_DIR or Azure Blob configuration."
        ) from exc
