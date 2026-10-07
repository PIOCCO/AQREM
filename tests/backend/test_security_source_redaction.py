from app.schemas.source import SourceResponse, redact_source_config


def test_redact_source_config_strips_tokens():
    raw = {"github_token": "ghp_secret", "demo_path": "/data"}
    safe = redact_source_config(raw)
    assert safe["github_token"] == "[redacted]"
    assert safe["demo_path"] == "/data"


def test_source_response_serializer_redacts_config():
    from datetime import UTC, datetime
    from uuid import uuid4

    row = SourceResponse(
        id=uuid4(),
        organization_id=uuid4(),
        project_id=None,
        name="x",
        source_type="github",
        scope="project",
        status="ready",
        config={"github_token": "ghp_abc", "repository_full_name": "o/r"},
        created_at=datetime.now(UTC),
    )
    dumped = row.model_dump()
    assert dumped["config"]["github_token"] == "[redacted]"
    assert dumped["config"]["repository_full_name"] == "o/r"
