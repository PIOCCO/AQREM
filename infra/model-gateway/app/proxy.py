from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx
from azure.identity import DefaultAzureCredential

from app.config import Settings

CHAT_SUFFIX = "/openai/deployments/{deployment}/chat/completions"
EMBED_SUFFIX = "/openai/deployments/{deployment}/embeddings"
ALLOWED_SUFFIXES = ("/chat/completions", "/embeddings")


class UpstreamError(Exception):
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body


def resolve_path(settings: Settings, path: str) -> tuple[str, str]:
    """Map /v1/chat-default/chat/completions -> deployment + azure path."""
    path = path.rstrip("/")
    if path.endswith("/chat/completions"):
        alias = settings.deployment_alias_chat
        if f"/{alias}/" in path or path.endswith(f"/{alias}/chat/completions"):
            deployment = settings.deployment_name_chat
            return deployment, CHAT_SUFFIX.format(deployment=deployment)
    if path.endswith("/embeddings"):
        alias = settings.deployment_alias_embeddings
        if f"/{alias}/" in path or path.endswith(f"/{alias}/embeddings"):
            deployment = settings.deployment_name_embeddings
            return deployment, EMBED_SUFFIX.format(deployment=deployment)
    raise ValueError("Path not allowed")


def _auth_headers(settings: Settings) -> dict[str, str]:
    if settings.gateway_env == "mock":
        return {"api-key": "mock"}
    if (settings.azure_openai_api_key or "").strip():
        return {"api-key": settings.azure_openai_api_key.strip()}
    if settings.azure_openai_use_managed_identity:
        token = DefaultAzureCredential().get_token("https://cognitiveservices.azure.com/.default").token
        return {"Authorization": f"Bearer {token}"}
    raise RuntimeError("Managed identity or AZURE_OPENAI_API_KEY required for gateway upstream")


async def forward_json(
    settings: Settings,
    azure_path: str,
    body: dict[str, Any],
) -> tuple[int, dict[str, Any], dict[str, int]]:
    if settings.gateway_env == "mock":
        return 200, {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 3}}, {
            "prompt_tokens": 5,
            "completion_tokens": 3,
        }
    url = f"{settings.azure_openai_endpoint.rstrip('/')}{azure_path}?api-version={settings.azure_openai_api_version}"
    headers = {"Content-Type": "application/json", **_auth_headers(settings)}
    if body.get("stream"):
        body = {**body, "stream_options": {"include_usage": True}}
    async with httpx.AsyncClient(timeout=settings.upstream_timeout_seconds) as client:
        resp = await client.post(url, headers=headers, json=body)
    text = resp.text
    if resp.status_code >= 400:
        raise UpstreamError(resp.status_code, text)
    data = json.loads(text)
    usage = data.get("usage") or {}
    counts = {
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
    }
    return resp.status_code, data, counts


async def forward_stream(
    settings: Settings,
    azure_path: str,
    body: dict[str, Any],
) -> AsyncIterator[bytes]:
    if settings.gateway_env == "mock":
        yield b'data: {"usage":{"prompt_tokens":5,"completion_tokens":3}}\n\n'
        yield b"data: [DONE]\n\n"
        return
    url = f"{settings.azure_openai_endpoint.rstrip('/')}{azure_path}?api-version={settings.azure_openai_api_version}"
    headers = {"Content-Type": "application/json", **_auth_headers(settings)}
    body = {**body, "stream": True, "stream_options": {"include_usage": True}}
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", url, headers=headers, json=body) as resp:
            if resp.status_code >= 400:
                chunk = await resp.aread()
                raise UpstreamError(resp.status_code, chunk.decode("utf-8", errors="replace"))
            async for chunk in resp.aiter_bytes():
                yield chunk
