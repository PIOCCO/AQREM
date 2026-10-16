"""
Core upload → index → chat flow (runs inside docker compose api container).

Requires: postgres, redis, worker, gateway, fake azure upstream.
"""

from __future__ import annotations

import os

import httpx
import pytest

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def api_base() -> str:
    return "http://127.0.0.1:8000"


@pytest.mark.asyncio
async def test_health_and_version(api_base: str):
    async with httpx.AsyncClient(timeout=30.0) as client:
        live = await client.get(f"{api_base}/health/live")
        assert live.status_code == 200
        ver = await client.get(f"{api_base}/api/v1/meta/version")
        assert ver.status_code == 200
        body = ver.json()
        assert body.get("environment") == "production"
        assert body.get("llm_provider") in {"openai", "gateway"}
        assert body.get("llm_provider") not in {"mock", "local", "fake", "test"}


def _gateway_health_url() -> str:
    """In compose exec, use service DNS; on host use published port (8088)."""
    base = (os.environ.get("GATEWAY_URL") or "http://model-gateway:8080").rstrip("/")
    return f"{base}/health/live"


@pytest.mark.asyncio
async def test_gateway_smoke():
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(_gateway_health_url())
        assert r.status_code == 200
