"""Production provider guardrails and organization-only retrieval."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.chat.messages import (
    format_empty_retrieval_message,
    format_no_indexed_documents_message,
    format_no_relevant_information_message,
)


def test_production_refuses_mock_provider():
    with pytest.raises(ValidationError, match="mock or fake"):
        Settings(
            app_env="production",
            llm_provider="mock",
            secret_key="x" * 32,
            gateway_url="https://gw.example.com",
        )


def test_production_refuses_local_provider():
    with pytest.raises(ValidationError, match="mock or fake"):
        Settings(
            app_env="production",
            llm_provider="local",
            secret_key="x" * 32,
        )


def test_production_refuses_fake_gateway_host():
    with pytest.raises(ValidationError, match="fake"):
        Settings(
            app_env="production",
            llm_provider="gateway",
            gateway_url="http://fake-azure-openai:8099",
            secret_key="x" * 32,
            azure_storage_connection_string="DefaultEndpointsProtocol=https;AccountName=x",
        )


def test_production_openai_requires_key():
    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        Settings(
            app_env="production",
            llm_provider="openai",
            secret_key="x" * 32,
            azure_storage_connection_string="DefaultEndpointsProtocol=https;AccountName=x",
        )


def test_production_openai_with_key_is_allowed():
    settings = Settings(
        app_env="production",
        llm_provider="openai",
        openai_api_key="sk-test-key-not-real",
        secret_key="x" * 32,
        azure_storage_connection_string="DefaultEndpointsProtocol=https;AccountName=x",
        database_url="postgresql+psycopg://u:p@db/aqrem",
        redis_url="redis://localhost:6379/0",
        app_public_base_url="https://app.example.com",
    )
    assert settings.llm_provider == "openai"


def test_development_allows_local_provider():
    settings = Settings(app_env="development", llm_provider="local")
    assert settings.llm_provider == "local"


def test_empty_messages_are_not_confusable():
    none = format_no_indexed_documents_message()
    miss = format_no_relevant_information_message()
    assert none == "No documents available"
    assert miss == "I couldn't find this in the company documents"
    assert none not in miss
    assert "company documents" not in none
    assert format_empty_retrieval_message(org_chunk_count=0) == none
    assert format_empty_retrieval_message(org_chunk_count=4) == miss


@pytest.mark.asyncio
async def test_employee_retrieval_ignores_project_and_acl(client, db_session):
    from app.core.roles import Role
    from app.core.security import create_access_token, hash_password
    from app.models.enums import EvidenceScope, SourceType
    from app.models.evidence import EvidenceItem
    from app.models.organization import Organization, OrganizationMembership, User
    from app.models.project import Project
    from app.models.source import Source

    org = Organization(name="Org Only", slug="org-only-retrieval")
    db_session.add(org)
    db_session.flush()
    admin = User(email="admin-org-only@example.com", hashed_password=hash_password("password"), full_name="Admin")
    employee = User(email="emp-org-only@example.com", hashed_password=hash_password("password"), full_name="Editor")
    db_session.add_all([admin, employee])
    db_session.flush()
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=admin.id, role=Role.ORG_ADMIN.value))
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=employee.id, role=Role.EDITOR.value))
    project = Project(organization_id=org.id, name="Private assistant")
    other = Project(organization_id=org.id, name="Other project")
    db_session.add_all([project, other])
    db_session.flush()
    source = Source(
        organization_id=org.id,
        project_id=project.id,
        name="Private documents",
        source_type=SourceType.FILE_UPLOAD.value,
        scope=EvidenceScope.PROJECT.value,
        visibility_mode="admins_only",
    )
    db_session.add(source)
    db_session.flush()
    db_session.add(
        EvidenceItem(
            organization_id=org.id,
            project_id=project.id,
            source_id=source.id,
            source_type=source.source_type,
            scope=EvidenceScope.PROJECT.value,
            file_name="gammal.pdf",
            file_path="gammal.pdf",
            content="Gammal Oussama is a senior software engineer with eight years of experience.",
            content_type="application/pdf",
            content_hash="org-only-hash",
            chunk_index=0,
            visibility_mode="admins_only",
        )
    )
    db_session.flush()

    token = create_access_token(str(employee.id), {"organization_id": str(org.id), "role": Role.EDITOR.value})
    res = client.post(
        "/api/v1/chat/ask",
        headers={"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)},
        json={"query": "who is gammal oussama", "project_id": str(other.id)},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["answer"] != "No documents available"
    assert "couldn't find this in the company documents" not in body["answer"].lower()
    assert "gammal" in body["answer"].lower()
    assert body.get("citations"), body
    assert any("gammal" in (c.get("file_name") or "").lower() for c in body["citations"])
