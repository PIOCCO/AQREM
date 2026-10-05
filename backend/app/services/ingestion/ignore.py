from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.source import IngestionIgnoreRule


def build_pathspec(db: Session, organization_id, project_id=None) -> PathSpec:
    settings = get_settings()
    patterns = [p.strip() for p in settings.default_ignore_patterns.split(",") if p.strip()]
    query = db.query(IngestionIgnoreRule).filter(
        IngestionIgnoreRule.organization_id == organization_id,
        IngestionIgnoreRule.enabled.is_(True),
    )
    if project_id:
        query = query.filter(
            (IngestionIgnoreRule.project_id.is_(None)) | (IngestionIgnoreRule.project_id == project_id)
        )
    else:
        query = query.filter(IngestionIgnoreRule.project_id.is_(None))
    for rule in query.all():
        patterns.append(rule.pattern)
    return PathSpec.from_lines(GitWildMatchPattern, patterns)


def should_ignore(path_spec: PathSpec, relative_path: str) -> bool:
    normalized = relative_path.replace("\\", "/").lstrip("./")
    return path_spec.match_file(normalized)
