from azure.storage.blob import BlobServiceClient

from app.services.storage.azure_client import resolve_blob_api_version
from app.services.storage.base import BlobStorage


class AzureBlobStorage(BlobStorage):
    def __init__(
        self,
        connection_string: str | None,
        container: str,
        *,
        api_version: str | None = None,
        account_url: str | None = None,
    ) -> None:
        blob_api_version = resolve_blob_api_version(connection_string or "", api_version)
        kwargs = {}
        if blob_api_version:
            kwargs["api_version"] = blob_api_version
        if (account_url or "").strip() and not (connection_string or "").strip():
            # Managed identity / workload identity; account_url may be a private-endpoint FQDN.
            from azure.identity import DefaultAzureCredential

            self.client = BlobServiceClient(
                account_url=account_url.strip(),
                credential=DefaultAzureCredential(exclude_interactive_browser_credential=True),
                **kwargs,
            )
        else:
            self.client = BlobServiceClient.from_connection_string(connection_string or "", **kwargs)
        self.container = container
        self._container_client = self.client.get_container_client(container)
        if not self._container_client.exists():
            self._container_client.create_container()

    def upload_bytes(self, blob_path: str, data: bytes, content_type: str) -> str:
        blob = self._container_client.get_blob_client(blob_path)
        blob.upload_blob(data, overwrite=True, content_type=content_type)
        return blob_path

    def download_bytes(self, blob_path: str) -> bytes:
        blob = self._container_client.get_blob_client(blob_path)
        return blob.download_blob().readall()

    def delete(self, blob_path: str) -> None:
        blob = self._container_client.get_blob_client(blob_path)
        blob.delete_blob(delete_snapshots="include")
