from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app


@patch("app.internal_auth.validate_entra_bearer", return_value={"oid": "sp"})
@patch("app.keys_api.connection")
def test_both_keys_active_during_rotation(mock_conn, _mock_entra, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("INTERNAL_ALLOWED_CIDRS", "10.0.0.0/8")
    cm = MagicMock()
    mock_conn.return_value.__enter__.return_value = cm
    client = TestClient(app)
    org = str(uuid.uuid4())
    with patch("app.internal_auth.trusted_client_ip", return_value="10.0.0.1"):
        for label in ("primary", "secondary"):
            res = client.post(
                "/internal/v1/keys/mint",
                json={"client_id": "acme", "organization_id": org, "label": label},
                headers={"Authorization": "Bearer t"},
            )
        assert res.status_code == 200
        assert res.json()["api_key_plaintext"].startswith("gw_")
