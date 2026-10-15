"""
Core upload → index → chat flow (runs inside docker compose api container).

Requires: postgres, redis, worker, gateway, fake azure upstream.
"""

from __future__ import annotations

import asyncio
import time
from uuid import uuid4

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
        assert body.get("llm_provider") == "gateway"


@pytest.mark.asyncio
async def test_gateway_smoke_from_host():
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get("http://127.0.0.1:8088/health/live")
        assert r.status_code == 200
