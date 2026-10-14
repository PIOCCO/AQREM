import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


@patch("app.internal_auth.validate_entra_bearer", return_value={"oid": "allowed"})
def test_spoofed_x_forwarded_for_rejected_without_trusted_proxy(_mock, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("INTERNAL_ALLOWED_CIDRS", "10.0.0.0/8")
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "10.0.0.0/8")
    client = TestClient(app)
    res = client.post(
        "/internal/v1/keys/mint",
        json={"client_id": "acme", "organization_id": str(uuid.uuid4()), "label": "primary"},
        headers={
            "Authorization": "Bearer fake",
            "X-Forwarded-For": "10.0.0.99",
        },
    )
    assert res.status_code == 403


@patch("app.internal_auth.trusted_client_ip", return_value="10.0.0.50")
@patch("app.internal_auth.validate_entra_bearer", return_value={"oid": "allowed"})
@patch("app.keys_api.connection")
def test_trusted_proxy_xff_used_when_peer_is_proxy(mock_conn, _mock, _ip, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("INTERNAL_PROVISIONING_ALLOWED_OBJECT_IDS", "allowed")
    monkeypatch.setenv("INTERNAL_ALLOWED_CIDRS", "10.0.0.0/8")
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "127.0.0.0/8")
    mock_conn.return_value.__enter__.return_value = mock_conn.return_value
    client = TestClient(app)
    res = client.post(
        "/internal/v1/keys/mint",
        json={"client_id": "acme", "organization_id": str(uuid.uuid4()), "label": "primary"},
        headers={"Authorization": "Bearer fake"},
    )
    assert res.status_code == 200
