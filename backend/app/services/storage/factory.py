from functools import lru_cache

from app.core.config import get_settings
from app.services.storage.base import BlobStorage
from app.services.storage.local import LocalBlobStorage


@lru_cache
def get_blob_storage() -> BlobStorage:
    settings = get_settings()
    if settings.azure_storage_connection_string:
        from app.services.storage.azure import AzureBlobStorage

        return AzureBlobStorage(
            connection_string=settings.azure_storage_connection_string,
            container=settings.azure_storage_container,
        )
    return LocalBlobStorage(settings.local_upload_dir)
