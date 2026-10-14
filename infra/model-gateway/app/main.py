from __future__ import annotations

import json
import logging
import time
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from app.auth import configure_auth_cache, verify_api_key
from app.config import get_settings
from app.db import ensure_schema
from app.limits import check_and_consume, configure_engine, record_usage
from app.keys_api import router as keys_router
from app.proxy import UpstreamError, forward_json, forward_stream, resolve_path

logger = logging.getLogger("aqrem.gateway")
app = FastAPI(title="AQREM Model Gateway", version="0.1.0")
app.include_router(keys_router)


@app.on_event("startup")
def startup() -> None:
    settings = get_settings()
    configure_engine(settings)
    configure_auth_cache(settings)
    ensure_schema(settings)
    logging.basicConfig(level=logging.INFO)


def _client_from_header(authorization: str | None, x_gateway_key: str | None) -> dict:
    raw = x_gateway_key
    if not raw and authorization and authorization.lower().startswith("bearer "):
        raw = authorization[7:].strip()
    if not raw:
        raise HTTPException(status_code=401, detail="Missing gateway API key")
    client = verify_api_key(get_settings(), raw)
    if not client:
        raise HTTPException(status_code=401, detail="Invalid gateway API key")
    return client


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready() -> dict[str, str]:
    settings = get_settings()
    ensure_schema(settings)
    return {"status": "ok"}


@app.post("/v1/{alias}/{endpoint:path}")
async def gateway_post(
    alias: str,
    endpoint: str,
    request: Request,
    authorization: str | None = Header(default=None),
    x_gateway_key: str | None = Header(default=None, alias="X-AQREM-Gateway-Key"),
) -> Response:
    settings = get_settings()
    path = f"/v1/{alias}/{endpoint}"
    if not (path.endswith("/chat/completions") or path.endswith("/embeddings")):
        raise HTTPException(status_code=404, detail="Path not allowed")

    body_bytes = await request.body()
    if len(body_bytes) > settings.max_request_bytes:
        raise HTTPException(status_code=413, detail="Request too large")

    client = _client_from_header(authorization, x_gateway_key)
    allowed, retry = check_and_consume(settings, client, requests=1, tokens=0)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"message": "Rate limit or budget exceeded"},
            headers={"Retry-After": str(retry or 60)},
        )

    try:
        _, azure_path = resolve_path(settings, path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        payload: dict[str, Any] = json.loads(body_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    started = time.perf_counter()
    stream = bool(payload.get("stream"))

    try:
        if stream:
            async def gen():
                usage_prompt = 0
                usage_completion = 0
                async for chunk in forward_stream(settings, azure_path, payload):
                    if chunk.startswith(b"data: ") and b'"usage"' in chunk:
                        try:
                            line = chunk.decode("utf-8").strip()
                            if line == "data: [DONE]":
                                yield chunk
                                continue
                            data = json.loads(line[6:])
                            usage = data.get("usage") or {}
                            usage_prompt = int(usage.get("prompt_tokens") or usage_prompt)
                            usage_completion = int(usage.get("completion_tokens") or usage_completion)
                        except json.JSONDecodeError:
                            pass
                    yield chunk
                record_usage(settings, client["client_id"], usage_prompt, usage_completion)
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                logger.info(
                    "gateway clientId=%s status=200 stream=1 latencyMs=%s promptTokens=%s completionTokens=%s",
                    client["client_id"],
                    elapsed_ms,
                    usage_prompt,
                    usage_completion,
                )

            return StreamingResponse(gen(), media_type="text/event-stream")

        status, data, counts = await forward_json(settings, azure_path, payload)
        record_usage(settings, client["client_id"], counts["prompt_tokens"], counts["completion_tokens"])
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "gateway clientId=%s status=%s stream=0 latencyMs=%s promptTokens=%s completionTokens=%s",
            client["client_id"],
            status,
            elapsed_ms,
            counts["prompt_tokens"],
            counts["completion_tokens"],
        )
        return JSONResponse(status_code=status, content=data)
    except UpstreamError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "gateway clientId=%s status=%s stream=%s latencyMs=%s promptTokens=0 completionTokens=0",
            client["client_id"],
            exc.status,
            int(stream),
            elapsed_ms,
        )
        return JSONResponse(status_code=exc.status, content={"message": "Upstream error"})
