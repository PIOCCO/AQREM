"""Minimal OpenAI-compatible fake gateway for integration tests."""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()
VALID_KEY = "test-gateway-key"
STATE: dict[str, Any] = {"mode": "ok", "stream_tokens": ["Hello", " ", "world"]}


def _auth(authorization: str | None) -> None:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing gateway API key")
    key = authorization[7:].strip()
    if key != VALID_KEY:
        raise HTTPException(status_code=401, detail="Invalid gateway API key")


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/{alias}/{endpoint:path}")
async def gateway_post(
    alias: str,
    endpoint: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    _auth(authorization)
    mode = STATE.get("mode", "ok")
    if mode == "429":
        return JSONResponse(
            status_code=429,
            content={"message": "Rate limit or budget exceeded"},
            headers={"Retry-After": "1"},
        )
    if mode == "401":
        raise HTTPException(status_code=401, detail="Invalid gateway API key")
    if mode == "500":
        return JSONResponse(status_code=500, content={"message": "Upstream error"})

    body = json.loads(await request.body())
    path = f"/v1/{alias}/{endpoint}"
    if path.endswith("/embeddings"):
        dim = int(STATE.get("embedding_dim", 384))
        vectors = [[0.01] * dim for _ in body.get("input", [])]
        return {
            "data": [{"embedding": v, "index": i} for i, v in enumerate(vectors)],
            "usage": {"prompt_tokens": 1, "total_tokens": 1},
        }

    if path.endswith("/chat/completions") and body.get("stream"):
        tokens: list[str] = list(STATE.get("stream_tokens") or ["Hi"])

        async def gen():
            for t in tokens:
                chunk = {
                    "choices": [{"delta": {"content": t}, "index": 0}],
                }
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    if path.endswith("/chat/completions"):
        payload = {
            "answer": "Structured answer from gateway.",
            "confidence": "high",
            "evidence_ids": [],
            "reasoning_summary": "From fake gateway.",
            "evidence_sufficiency": "sufficient",
        }
        return {
            "choices": [{"message": {"content": json.dumps(payload)}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }

    raise HTTPException(status_code=404, detail="Path not allowed")
