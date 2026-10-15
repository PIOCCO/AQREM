from app.services.storage.azure_client import (
    AZURITE_BLOB_API_VERSION,
    is_azurite_connection_string,
    resolve_blob_api_version,
)

AZURITE = (
    "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
    "AccountKey=x==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
)


def test_detects_azurite_connection_string():
    assert is_azurite_connection_string(AZURITE)
    assert not is_azurite_connection_string(
        "DefaultEndpointsProtocol=https;AccountName=prod;AccountKey=x==;EndpointSuffix=core.windows.net"
    )


def test_azurite_gets_compatible_api_version():
    assert resolve_blob_api_version(AZURITE, None) == AZURITE_BLOB_API_VERSION


def test_explicit_api_version_wins():
    assert resolve_blob_api_version(AZURITE, "2023-11-03") == "2023-11-03"
