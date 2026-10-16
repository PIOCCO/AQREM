import httpx
import pytest

from app.core.config import Settings
from app.services.system.fleet import parse_fleet, poll_fleet


def test_parse_fleet_ignores_bad_entries():
    assert parse_fleet("a=https://a.example.com/, bad=ftp://x, =https://b.example.com") == [
        ("a", "https://a.example.com"), ("b.example.com", "https://b.example.com")]


@pytest.mark.asyncio
async def test_poll_fleet_reports_version_health_and_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "down.example.com":
            raise httpx.ConnectError("boom")
        if request.url.path == "/api/v1/version":
            return httpx.Response(200, json={"version": "2026.10.1", "deployment_mode": "dedicated", "schema_version": 2})
        return httpx.Response(200, json={"status": "degraded", "degraded": ["broker"],
                                         "dependencies": {"database": {"status": "ok"}, "broker": {"status": "down"},
                                                          "license": {"status": "valid"}}})

    s = Settings(fleet_environments="contoso=https://contoso.example.com,down=https://down.example.com")
    rows = await poll_fleet(s, transport=httpx.MockTransport(handler))
    by = {r["name"]: r for r in rows}
    assert by["contoso"]["version"] == "2026.10.1"
    assert by["contoso"]["status"] == "degraded" and by["contoso"]["dependencies"]["broker"] == "down"
    assert by["contoso"]["license"] == "valid"
    assert by["down"]["status"] == "unreachable" and by["down"]["error"] == "ConnectError"
