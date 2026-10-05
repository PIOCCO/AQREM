from enum import StrEnum


class Role(StrEnum):
    ORG_ADMIN = "ORG_ADMIN"
    EDITOR = "EDITOR"
    REVIEWER = "REVIEWER"
    VIEWER = "VIEWER"


ROLE_HIERARCHY = {
    Role.VIEWER: 0,
    Role.REVIEWER: 1,
    Role.EDITOR: 2,
    Role.ORG_ADMIN: 3,
}


def role_at_least(user_role: Role, required: Role) -> bool:
    return ROLE_HIERARCHY[user_role] >= ROLE_HIERARCHY[required]
