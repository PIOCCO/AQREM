from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Query

from app.services.access_control.constants import (
    VISIBILITY_ADMINS_ONLY,
    VISIBILITY_ALL_STAFF,
    VISIBILITY_GROUPS,
    VISIBILITY_USERS,
)
from app.services.access_control.context import UserAccessContext


def evidence_acl_filter(query: Query, access: UserAccessContext, model) -> Query:
    if access.is_org_admin:
        return query
    user_id = access.user_id
    group_ids = list(access.group_ids)
    clauses = [model.visibility_mode == VISIBILITY_ALL_STAFF]
    clauses.append(and_(model.visibility_mode == VISIBILITY_USERS, model.visibility_user_ids.any(user_id)))
    if group_ids:
        clauses.append(
            and_(
                model.visibility_mode == VISIBILITY_GROUPS,
                model.visibility_group_ids.overlap(group_ids),
            )
        )
    return query.filter(or_(*clauses))


def acl_sql_fragment(*, prefix: str = "") -> str:
    col = f"{prefix}visibility_mode" if prefix else "visibility_mode"
    gcol = f"{prefix}visibility_group_ids" if prefix else "visibility_group_ids"
    ucol = f"{prefix}visibility_user_ids" if prefix else "visibility_user_ids"
    return f"""
    (
      :is_org_admin = true
      OR {col} = 'all_staff'
      OR ({col} = 'users' AND :user_id = ANY({ucol}))
      OR ({col} = 'groups' AND cardinality(CAST(:group_ids AS uuid[])) > 0 AND {gcol} && CAST(:group_ids AS uuid[]))
    )
    """


def acl_bind_params(access: UserAccessContext) -> dict:
    return {
        "is_org_admin": access.is_org_admin,
        "user_id": access.user_id,
        "group_ids": list(access.group_ids),
    }


def can_access_record(
    access: UserAccessContext,
    *,
    visibility_mode: str,
    visibility_group_ids: list[UUID] | None,
    visibility_user_ids: list[UUID] | None,
) -> bool:
    if access.is_org_admin:
        return True
    mode = visibility_mode or VISIBILITY_ADMINS_ONLY
    if mode == VISIBILITY_ALL_STAFF:
        return True
    if mode == VISIBILITY_ADMINS_ONLY or mode == "unset":
        return False
    if mode == VISIBILITY_USERS:
        return access.user_id in (visibility_user_ids or [])
    if mode == VISIBILITY_GROUPS:
        allowed = set(visibility_group_ids or [])
        return bool(allowed.intersection(access.group_ids))
    return False
