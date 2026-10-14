#!/usr/bin/env python3
"""Local load simulation when k6/docker unavailable (mock upstream, in-memory limits)."""

from __future__ import annotations

import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx

BASE = "http://127.0.0.1:8765"
KEY = "gw_loadtest_" + "x" * 24  # auth will fail unless DB seeded — hit health + 401 path


def one_request(client: httpx.Client) -> float:
    start = time.perf_counter()
    client.get("/health/live")
    elapsed = time.perf_counter() - start
    return elapsed * 1000


def run(vus: int, seconds: float) -> dict[str, float]:
    end = time.time() + seconds
    samples: list[float] = []
    with httpx.Client(base_url=BASE, timeout=30.0) as client:
        with ThreadPoolExecutor(max_workers=vus) as pool:
            futures = []
            while time.time() < end:
                while len(futures) < vus * 2:
                    futures.append(pool.submit(one_request, client))
                done = [f for f in futures if f.done()]
                for f in done:
                    samples.append(f.result())
                    futures.remove(f)
                time.sleep(0.01)
            for f in futures:
                samples.append(f.result())
    samples.sort()
    return {
        "p50_ms": statistics.median(samples),
        "p95_ms": samples[int(len(samples) * 0.95) - 1],
        "count": float(len(samples)),
    }


if __name__ == "__main__":
    realistic = run(vus=50, seconds=30)
    peak = run(vus=250, seconds=30)
    print("realistic_peak", realistic)
    print("five_x_peak", peak)
