#!/usr/bin/env python3
"""Post-deploy smoke checks for model gateway integration (no secrets logged)."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import Settings
from app.core.gateway_config import inspect_gateway
from app.services.llm.base import AnswerRequest
from app.services.llm.factory import get_llm_provider, reset_llm_provider_cache


def _pass(label: str) -> None:
    print(f"PASS  {label}")


def _fail(label: str, detail: str = "") -> None:
    msg = f"FAIL  {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)


async def _run() -> int:
    fails = 0
    settings = Settings()
    provider_name = settings.llm_provider.lower().strip()

    if provider_name not in {"gateway", "mock", "local", "azure", "openai"}:
        _fail("llm_provider", f"unexpected {provider_name}")
        fails += 1
    else:
        _pass(f"llm_provider={provider_name}")

    if provider_name == "gateway":
        status = inspect_gateway(settings)
        if status.configured:
            _pass("gateway_config")
        else:
            _fail("gateway_config", ", ".join(status.missing))
            fails += 1

    reset_llm_provider_cache()
    try:
        llm = get_llm_provider()
    except Exception as exc:
        _fail("get_llm_provider", type(exc).__name__)
        return fails + 1
    _pass("get_llm_provider")

    try:
        vectors = await llm.embed(["connectivity probe"])
        if vectors and len(vectors[0]) == settings.embedding_dimensions:
            _pass("embeddings")
        else:
            _fail("embeddings", "dimension mismatch")
            fails += 1
    except Exception as exc:
        _fail("embeddings", type(exc).__name__)
        fails += 1

    try:
        answer = await llm.generate_answer(
            AnswerRequest(
                question="Smoke test question?",
                evidence_blocks=[
                    {
                        "id": "00000000-0000-4000-8000-000000000001",
                        "content": "Smoke policy requires weekly backups.",
                        "untrusted_data_notice": "untrusted",
                    }
                ],
            )
        )
        if answer.answer.strip():
            _pass("chat_completion")
        else:
            _fail("chat_completion", "empty answer")
            fails += 1
    except Exception as exc:
        _fail("chat_completion", type(exc).__name__)
        fails += 1

    if provider_name == "gateway" and hasattr(llm, "stream_chat_tokens"):
        try:
            tokens = []
            async for t in llm.stream_chat_tokens(
                messages=[
                    {"role": "system", "content": "Reply with one word."},
                    {"role": "user", "content": "Say OK."},
                ]
            ):
                tokens.append(t)
            if tokens:
                _pass("streaming")
            else:
                _fail("streaming", "no tokens")
                fails += 1
        except Exception as exc:
            _fail("streaming", type(exc).__name__)
            fails += 1

    wrong_key = os.environ.get("GATEWAY_WRONG_KEY_TEST", "")
    if provider_name == "gateway" and wrong_key:
        from app.services.llm.gateway import GatewayLLMProvider

        bad = GatewayLLMProvider(settings, api_key=wrong_key)
        try:
            await bad.embed(["x"])
            _fail("wrong_key_rejected", "expected 401")
            fails += 1
        except Exception:
            _pass("wrong_key_rejected")

    return fails


def main() -> int:
    fails = asyncio.run(_run())
    print(f"\nSummary: {fails} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
