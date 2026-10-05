from abc import ABC, abstractmethod


class BlobStorage(ABC):
    @abstractmethod
    def upload_bytes(self, blob_path: str, data: bytes, content_type: str) -> str: ...

    @abstractmethod
    def download_bytes(self, blob_path: str) -> bytes: ...

    @abstractmethod
    def delete(self, blob_path: str) -> None: ...
