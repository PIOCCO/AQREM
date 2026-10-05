from uuid import UUID

from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.tenant import TenantContext
from app.models.enums import SourceType
from app.models.source import GitHubRepoConfig, Source
from app.schemas.source import GitHubRepoConnectRequest, SourceCreate


def create_source_record(
    db: Session,
    tenant: TenantContext,
    payload: SourceCreate,
    *,
    commit: bool = True,
) -> Source:
    source = Source(
        organization_id=tenant.organization_id,
        project_id=payload.project_id,
        name=payload.name,
        source_type=payload.source_type.value,
        scope=payload.scope.value,
        config=payload.config,
    )
    db.add(source)
    if commit:
        db.commit()
        db.refresh(source)
        record_audit(
            db,
            organization_id=tenant.organization_id,
            user_id=tenant.user_id,
            action="source_connected",
            resource_type="source",
            resource_id=str(source.id),
        )
        db.commit()
    else:
        db.flush()
    return source


def connect_github_to_source(
    db: Session,
    tenant: TenantContext,
    source: Source,
    payload: GitHubRepoConnectRequest,
) -> Source:
    if source.source_type != SourceType.GITHUB.value:
        raise ValueError("Source is not GitHub type")

    config = dict(source.config)
    if payload.access_token:
        config["github_token_ref"] = "inline-dev-token"
        config["github_token"] = payload.access_token

    source.config = config
    existing = db.query(GitHubRepoConfig).filter(GitHubRepoConfig.source_id == source.id).first()
    if existing:
        existing.repository_full_name = payload.repository_full_name
        existing.default_branch = payload.branch
    else:
        db.add(
            GitHubRepoConfig(
                organization_id=tenant.organization_id,
                source_id=source.id,
                repository_full_name=payload.repository_full_name,
                default_branch=payload.branch,
            )
        )
    db.commit()
    db.refresh(source)
    return source
