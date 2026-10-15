from functools import lru_cache

from app.core.config import get_settings, is_local_prod_stack
from app.services.storage.base import BlobStorage
from app.services.storage.local import LocalBlobStorage


@lru_cache
def get_blob_storage() -> BlobStorage:
    settings = get_settings()
    upload_dir = (settings.local_upload_dir or "").strip()
    if is_local_prod_stack() and upload_dir:
        return LocalBlobStorage(upload_dir)
    if settings.use_azure_blob_storage:
        from app.services.storage.azure import AzureBlobStorage

        return AzureBlobStorage(
            connection_string=(settings.azure_storage_connection_string or "").strip(),
            container=settings.azure_storage_container,
            api_version=settings.azure_storage_blob_api_version,
        )
    return LocalBlobStorage(settings.local_upload_dir)


def clear_blob_storage_cache() -> None:
    get_blob_storage.cache_clear()
