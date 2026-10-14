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
        headers={"Authorization": "Bearer x"},
    )
    assert res.status_code == 403


@patch("app.internal_auth.validate_entra_bearer", return_value={"oid": "sp"})
@patch("app.keys_api.connection")
def test_internal_mint_allowed_from_private_cidr(mock_conn, _mock_entra, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    mock_conn.return_value.__enter__.return_value = mock_conn.return_value
    monkeypatch.setenv("INTERNAL_ALLOWED_CIDRS", "10.0.0.0/8")
    client = TestClient(app)
    with patch("app.internal_auth.trusted_client_ip", return_value="10.1.2.3"):
        res = client.post(
            "/internal/v1/keys/mint",
            json={"client_id": "acme", "organization_id": str(uuid.uuid4()), "label": "primary"},
            headers={"Authorization": "Bearer t"},
        )
    assert res.status_code == 200
