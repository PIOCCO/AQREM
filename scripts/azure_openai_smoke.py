#!/usr/bin/env python3
"""Optional live Azure OpenAI smoke test — runs only when explicitly configured.

Usage:
  export LLM_PROVIDER=azure
  export AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
  export AZURE_OPENAI_API_KEY=<key>   # or AZURE_OPENAI_USE_MANAGED_IDENTITY=true
  export AZURE_OPENAI_CHAT_DEPLOYMENT=<chat-deployment>
  export AZURE_OPENAI_EMBEDDING_DEPLOYMENT=<embedding-deployment>
  python3 scripts/azure_openai_smoke.py

Exits 0 on success, 1 on misconfiguration, 2 on API failure.
Does not print secrets.
"""

from __future__ import annotations

import asyncio
import os
import sys


def _bootstrap_path() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    backend = os.path.join(root, "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)


async def main() -> int:
    _bootstrap_path()
    from app.core.config import Settings
    from app.core.llm_config import inspect_azure_openai
    from app.services.llm.azure_openai import AzureOpenAIProvider
    from app.services.llm.base import AnswerRequest

    settings = Settings()
    if settings.llm_provider.lower() != "azure":
        print("Set LLM_PROVIDER=azure to run this smoke test.", file=sys.stderr)
        return 1

    status = inspect_azure_openai(settings)
    if not status.configured:
        print("Incomplete Azure OpenAI configuration:", ", ".join(status.missing), file=sys.stderr)
        return 1

    provider = AzureOpenAIProvider(settings)
    print(f"Endpoint host: {status.endpoint_host}")
    print(f"Auth mode: {status.auth_mode}")

    vectors = await provider.embed(["AQREM connectivity probe"])
    print(f"Embedding dimensions: {len(vectors[0])}")

    answer = await provider.generate_answer(
        AnswerRequest(
            question="Reply with JSON only: one-word ping.",
            evidence_blocks=[
                {
                    "id": "00000000-0000-4000-8000-000000000001",
                    "file_path": "smoke.txt",
                    "content": "This is a synthetic evidence block for connectivity testing.",
                }
            ],
        )
    )
    print(f"Chat response sufficiency={answer.evidence_sufficiency} confidence={answer.confidence}")
    print("Azure OpenAI smoke test succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
