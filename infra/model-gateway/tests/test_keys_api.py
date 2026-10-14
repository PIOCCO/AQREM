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


def test_mint_requires_token(client):
    res = client.post(
        "/internal/v1/keys/mint",
        json={"client_id": "acme", "organization_id": str(uuid.uuid4()), "label": "primary"},
    )
    assert res.status_code == 403


@patch("app.keys_api.connection")
@patch("app.keys_api.get_settings")
def test_mint_returns_plaintext_once(mock_settings, mock_conn, client):
    mock_settings.return_value.internal_provisioning_token = "secret"
    mock_settings.return_value.internal_allowed_cidrs = "10.0.0.0/8"
    cm = MagicMock()
    mock_conn.return_value.__enter__.return_value = cm
    res = client.post(
        "/internal/v1/keys/mint",
        headers={"X-Platform-Token": "secret", "X-Forwarded-For": "10.0.0.1"},
        json={"client_id": "acme", "organization_id": str(uuid.uuid4()), "label": "primary"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["api_key_plaintext"].startswith("gw_")
    assert body["label"] == "primary"
