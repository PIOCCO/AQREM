#!/usr/bin/env python3
"""Seed a synthetic Acme Software demo (run against a running API with valid credentials)."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import httpx


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed MVP demo organization data")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    async with httpx.AsyncClient(base_url=args.base_url, timeout=120.0) as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": args.email, "password": args.password},
        )
        login.raise_for_status()
        token = login.json()["access_token"]
        org_id = login.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        project = await client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Acme SaaS Platform", "description": "Customer-facing SaaS product"},
        )
        project.raise_for_status()
        project_id = project.json()["id"]

        source = await client.post(
            "/api/v1/sources",
            headers=headers,
            json={
                "name": "Demo repository",
                "source_type": "folder_archive",
                "project_id": project_id,
                "scope": "project",
            },
        )
        source.raise_for_status()

        questionnaire = await client.post(
            "/api/v1/questionnaires",
            headers=headers,
            json={
                "name": "Customer Security Assessment",
                "project_id": project_id,
                "recipient": "Enterprise prospect",
            },
        )
        questionnaire.raise_for_status()
        qid = questionnaire.json()["id"]

        fixture = Path(__file__).resolve().parents[1] / "tests/fixtures/customer_security_assessment.csv"
        files = {"file": (fixture.name, fixture.read_bytes(), "text/csv")}
        upload = await client.post(
            f"/api/v1/questionnaires/{qid}/upload",
            headers={"Authorization": f"Bearer {token}", "X-Organization-Id": org_id},
            files=files,
        )
        upload.raise_for_status()
        print("Demo seed complete:", upload.json())


if __name__ == "__main__":
    asyncio.run(main())
