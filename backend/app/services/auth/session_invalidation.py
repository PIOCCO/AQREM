from sqlalchemy.orm import Session

from app.models.organization import OrganizationMembership, User


def invalidate_user_sessions(db: Session, user: User) -> None:
    user.platform_auth_version = int(getattr(user, "platform_auth_version", 1) or 1) + 1
    memberships = db.query(OrganizationMembership).filter(OrganizationMembership.user_id == user.id).all()
    for membership in memberships:
        membership.auth_version = int(membership.auth_version or 1) + 1
