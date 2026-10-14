from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.auth import configure_auth_cache
from app.config import Settings
from app.main import app


@patch("app.keys_api.connection")
def test_both_keys_active_during_rotation(mock_conn, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("INTERNAL_PROVISIONING_TOKEN", "secret")
    monkeypatch.setenv("INTERNAL_ALLOWED_CIDRS", "10.0.0.0/8")
    configure_auth_cache(Settings(azure_openai_endpoint="https://x", key_validation_cache_seconds=60))
    cm = MagicMock()
    mock_conn.return_value.__enter__.return_value = cm

    client = TestClient(app)
    org = str(uuid.uuid4())
    for label in ("primary", "secondary"):
        res = client.post(
            "/internal/v1/keys/mint",
            json={"client_id": "acme", "organization_id": org, "label": label},
            headers={"X-Platform-Token": "secret", "X-Forwarded-For": "10.0.0.1"},
        )
        assert res.status_code == 200
        assert res.json()["api_key_plaintext"].startswith("gw_")
