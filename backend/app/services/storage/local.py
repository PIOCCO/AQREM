from pathlib import Path

from app.services.storage.base import BlobStorage
from app.services.storage.path_utils import resolve_under_root


class LocalBlobStorage(BlobStorage):
    def __init__(self, root_dir: str) -> None:
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, blob_path: str) -> Path:
        full = resolve_under_root(self.root, blob_path)
        full.parent.mkdir(parents=True, exist_ok=True)
        return full

    def upload_bytes(self, blob_path: str, data: bytes, content_type: str) -> str:
        path = self._path(blob_path)
        path.write_bytes(data)
        return str(path)

    def download_bytes(self, blob_path: str) -> bytes:
        return self._path(blob_path).read_bytes()

    def delete(self, blob_path: str) -> None:
        path = self._path(blob_path)
        if path.exists():
            path.unlink()
