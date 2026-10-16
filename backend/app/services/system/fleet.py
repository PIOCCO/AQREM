"""Fleet view: poll dedicated environments' public /api/v1/version and /health.

FLEET_ENVIRONMENTS="contoso=https://contoso.aqrem.example,fabrikam=https://..."
Only metadata is read (version, status, dependency states); the endpoints are unauthenticated
and contain no tenant data or secrets. Last results are kept in memory.
"""

from __future__ import annotations

import asyncio
import time
from urllib.parse import urlparse

import httpx

from app.core.config import Settings, get_settings

_last: dict[str, dict] = {}


def parse_fleet(raw: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        name, _, url = part.partition("=")
        url = url.strip().rstrip("/")
        p = urlparse(url)
        if p.scheme not in {"http", "https"} or not p.netloc:
            continue
        out.append((name.strip() or p.netloc, url))
    return out


async def _probe(client: httpx.AsyncClient, name: str, url: str) -> dict:
    row: dict = {"name": name, "url": url, "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        v = await client.get(f"{url}/api/v1/version")
        v.raise_for_status()
        vj = v.json()
        row.update(version=vj.get("version"), deployment_mode=vj.get("deployment_mode"),
                   schema_version=vj.get("schema_version"))
        h = await client.get(f"{url}/health")
        hj = h.json() if h.headers.get("content-type", "").startswith("application/json") else {}
        deps = hj.get("dependencies") or {}
        row.update(status=hj.get("status", "unknown"), degraded=hj.get("degraded", []),
                   dependencies={k: (d or {}).get("status") for k, d in deps.items()},
                   license=(deps.get("license") or {}).get("status"))
    except Exception as exc:
        row.update(status="unreachable", error=type(exc).__name__)
    row["last_ok_at"] = row["checked_at"] if row.get("status") == "ok" else (_last.get(url) or {}).get("last_ok_at")
    _last[url] = row
    return row


async def poll_fleet(settings: Settings | None = None, *, transport: httpx.AsyncBaseTransport | None = None) -> list[dict]:
    settings = settings or get_settings()
    envs = parse_fleet(settings.fleet_environments)
    if not envs:
        return []
    async with httpx.AsyncClient(timeout=6.0, transport=transport, follow_redirects=False) as client:
        return list(await asyncio.gather(*(_probe(client, n, u) for n, u in envs)))


def last_results() -> list[dict]:
    return list(_last.values())
