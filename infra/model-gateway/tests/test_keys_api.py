from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("INTERNAL_ALLOWED_CIDRS", "127.0.0.0/8,10.0.0.0/8")
    return TestClient(app)


@patch("app.internal_auth.trusted_client_ip", return_value="10.0.0.1")
@patch("app.internal_auth.validate_entra_bearer")
def test_mint_requires_entra(_mock_entra, _mock_ip, client):
    _mock_entra.side_effect = __import__("fastapi").HTTPException(status_code=401, detail="Missing bearer token")
    res = client.post(
        "/internal/v1/keys/mint",
        json={"client_id": "acme", "organization_id": str(uuid.uuid4()), "label": "primary"},
    )
    assert res.status_code == 401


@patch("app.internal_auth.validate_entra_bearer", return_value={"oid": "sp"})
@patch("app.keys_api.connection")
@patch("app.keys_api.get_settings")
def test_mint_returns_plaintext_once(mock_settings, mock_conn, _mock_entra, client):
    mock_settings.return_value.internal_allowed_cidrs = "127.0.0.0/8,10.0.0.0/8"
    mock_settings.return_value.trusted_proxy_cidrs = ""
    cm = MagicMock()
    mock_conn.return_value.__enter__.return_value = cm
    with patch("app.internal_auth.trusted_client_ip", return_value="10.0.0.1"):
        res = client.post(
            "/internal/v1/keys/mint",
            headers={"Authorization": "Bearer token"},
            json={"client_id": "acme", "organization_id": str(uuid.uuid4()), "label": "primary"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["api_key_plaintext"].startswith("gw_")
    assert body["label"] == "primary"
