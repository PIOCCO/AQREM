from __future__ import annotations

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def test_internal_mint_blocked_from_public_ip(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("INTERNAL_ALLOWED_CIDRS", "10.0.0.0/8")
    client = TestClient(app)
    res = client.post(
        "/internal/v1/keys/mint",
        json={"client_id": "acme", "organization_id": str(uuid.uuid4()), "label": "primary"},
        headers={"X-Platform-Token": "secret"},
    )
    assert res.status_code == 403


@patch("app.keys_api.connection")
def test_internal_mint_allowed_from_private_cidr(mock_conn, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("INTERNAL_PROVISIONING_TOKEN", "secret")
    monkeypatch.setenv("INTERNAL_ALLOWED_CIDRS", "127.0.0.0/8,10.0.0.0/8")
    cm = mock_conn.return_value.__enter__.return_value
    client = TestClient(app)
    res = client.post(
        "/internal/v1/keys/mint",
        json={"client_id": "acme", "organization_id": str(uuid.uuid4()), "label": "primary"},
        headers={"X-Platform-Token": "secret", "X-Forwarded-For": "10.1.2.3"},
    )
    assert res.status_code == 200
