from uuid import UUID

from sqlalchemy.orm import Session

from app.models.access_group import AccessGroup
from app.services.access_control.constants import DEFAULT_GROUP_SPECS


def ensure_default_access_groups(db: Session, organization_id: UUID) -> list[AccessGroup]:
    existing = (
        db.query(AccessGroup).filter(AccessGroup.organization_id == organization_id, AccessGroup.is_system.is_(True)).count()
    )
    if existing >= len(DEFAULT_GROUP_SPECS):
        return db.query(AccessGroup).filter(AccessGroup.organization_id == organization_id).all()
    created: list[AccessGroup] = []
    for name, slug in DEFAULT_GROUP_SPECS:
        row = (
            db.query(AccessGroup)
            .filter(AccessGroup.organization_id == organization_id, AccessGroup.slug == slug)
            .first()
        )
        if row is None:
            row = AccessGroup(organization_id=organization_id, name=name, slug=slug, is_system=True)
            db.add(row)
            created.append(row)
    if created:
        db.flush()
    return created
