"""Local fake Azure OpenAI upstream for model-gateway (no real Azure)."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(title="Fake Azure OpenAI", version="0.1.0")

EMBED_DIM = int(os.environ.get("FAKE_EMBED_DIM", "384"))
MODE = os.environ.get("FAKE_AZURE_MODE", "ok")


def _mode_from_header(x_fake_mode: str | None) -> str:
    return (x_fake_mode or MODE or "ok").strip().lower()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/openai/deployments/{deployment}/embeddings")
async def embeddings(
    deployment: str,
    request: Request,
    x_fake_mode: str | None = Header(default=None, alias="X-Fake-Azure-Mode"),
) -> JSONResponse:
    mode = _mode_from_header(x_fake_mode)
    if mode == "429":
        return JSONResponse(status_code=429, content={"error": {"message": "rate limit"}}, headers={"Retry-After": "2"})
    if mode == "500":
        return JSONResponse(status_code=500, content={"error": {"message": "upstream failure"}})
    body = await request.json()
    texts = body.get("input") or []
    if isinstance(texts, str):
        texts = [texts]
    data = [{"embedding": [0.01] * EMBED_DIM, "index": i} for i, _ in enumerate(texts)]
    return JSONResponse(
        content={"data": data, "usage": {"prompt_tokens": len(texts), "total_tokens": len(texts)}},
    )


def _structured_answer_from_evidence(user_content: str) -> dict[str, Any]:
    try:
        payload = json.loads(user_content)
    except json.JSONDecodeError:
        payload = {}
    evidence = payload.get("evidence") or []
    question = str(payload.get("question") or "")
    ids = [str(b.get("id")) for b in evidence if b.get("id")]
    if not evidence:
        return {
            "answer": "I couldn't find this in the documents you have access to.",
            "confidence": "low",
            "evidence_ids": [],
            "reasoning_summary": "No evidence supplied.",
            "evidence_sufficiency": "insufficient",
        }
    snippet = str(evidence[0].get("content") or "")[:200]
    return {
        "answer": f"Based on the indexed documents: {snippet}",
        "confidence": "high",
        "evidence_ids": ids[:3],
        "reasoning_summary": "Answer derived from retrieved evidence blocks.",
        "evidence_sufficiency": "sufficient",
    }


@app.post("/openai/deployments/{deployment}/chat/completions")
async def chat(
    deployment: str,
    request: Request,
    x_fake_mode: str | None = Header(default=None, alias="X-Fake-Azure-Mode"),
):
    mode = _mode_from_header(x_fake_mode)
    if mode == "429":
        return JSONResponse(status_code=429, content={"error": {"message": "rate limit"}}, headers={"Retry-After": "2"})
    if mode == "500":
        return JSONResponse(status_code=500, content={"error": {"message": "upstream failure"}})
    body = await request.json()
    messages = body.get("messages") or []
    user_content = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_content = str(m.get("content") or "")
            break
    if body.get("stream"):

        async def stream_gen():
            text = _structured_answer_from_evidence(user_content).get("answer", "OK")
            for word in text.split():
                chunk = {
                    "choices": [{"delta": {"content": word + " "}, "index": 0}],
                }
                yield f"data: {json.dumps(chunk)}\n\n"
            usage = {"usage": {"prompt_tokens": 12, "completion_tokens": len(text.split())}}
            yield f"data: {json.dumps(usage)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream_gen(), media_type="text/event-stream")

    structured = _structured_answer_from_evidence(user_content)
    if body.get("response_format", {}).get("type") == "json_object":
        content = json.dumps(structured)
    else:
        content = structured["answer"]
    return JSONResponse(
        content={
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 30},
        }
    )
