"""Organization admin: groups and document visibility."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.dependencies import require_org_admin
from app.core.org_admin_errors import org_admin_error
from app.core.roles import Role
from app.core.tenant import TenantContext
from app.models.access_group import AccessGroup, AccessGroupMembership
from app.models.client_admin import ClientDocument
from app.models.evidence import EvidenceItem
from app.models.organization import OrganizationMembership, User
from app.schemas.access_control import (
    AccessGroupCreateRequest,
    AccessGroupMembersRequest,
    AccessGroupResponse,
    BulkDocumentVisibilityRequest,
    DocumentVisibilityRequest,
    PreviewAsRequest,
    PreviewAsResponse,
)
from app.services.access_control.constants import (
    VISIBILITY_ADMINS_ONLY,
    VISIBILITY_ALL_STAFF,
    VISIBILITY_GROUPS,
    VISIBILITY_USERS,
)
from app.services.access_control.context import UserAccessContext, build_access_context
from app.services.access_control.document_acl import apply_acl_to_evidence_for_document
from app.services.access_control.groups import ensure_default_access_groups
from app.services.access_control.policy import evidence_acl_filter
from app.services.chat.service import ChatAskService
from app.tenant_store.deps import get_tenant_db

from app.api.v1.org_admin import _require_org_admin_surface

router = APIRouter()


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48]
    return base or "group"


def _validate_visibility(payload: DocumentVisibilityRequest) -> None:
    if payload.visibility_mode not in {
        VISIBILITY_ALL_STAFF,
        VISIBILITY_GROUPS,
        VISIBILITY_USERS,
        VISIBILITY_ADMINS_ONLY,
    }:
        raise org_admin_error(code="INVALID_VISIBILITY", message="Unknown visibility setting.")
    if payload.visibility_mode == VISIBILITY_GROUPS and not payload.visibility_group_ids:
        raise org_admin_error(code="GROUPS_REQUIRED", message="Pick at least one group.")
    if payload.visibility_mode == VISIBILITY_USERS and not payload.visibility_user_ids:
        raise org_admin_error(code="USERS_REQUIRED", message="Pick at least one person.")


@router.get("/groups", response_model=list[AccessGroupResponse])
def list_groups(
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
) -> list[AccessGroupResponse]:
    ensure_default_access_groups(db, tenant.organization_id)
    db.commit()
    groups = (
        db.query(AccessGroup)
        .filter(AccessGroup.organization_id == tenant.organization_id)
        .order_by(AccessGroup.name.asc())
        .all()
    )
    out: list[AccessGroupResponse] = []
    for g in groups:
        count = (
            db.query(AccessGroupMembership)
            .filter(
                AccessGroupMembership.organization_id == tenant.organization_id,
                AccessGroupMembership.group_id == g.id,
            )
            .count()
        )
        out.append(
            AccessGroupResponse(id=g.id, name=g.name, slug=g.slug, is_system=g.is_system, member_count=count)
        )
    return out


@router.post("/groups", response_model=AccessGroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: AccessGroupCreateRequest,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
) -> AccessGroupResponse:
    slug = _slugify(payload.name)
    existing = (
        db.query(AccessGroup)
        .filter(AccessGroup.organization_id == tenant.organization_id, AccessGroup.slug == slug)
        .first()
    )
    if existing:
        raise org_admin_error(code="DUPLICATE_GROUP", message="A group with a similar name already exists.")
    group = AccessGroup(organization_id=tenant.organization_id, name=payload.name.strip(), slug=slug, is_system=False)
    db.add(group)
    db.flush()
    record_audit(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="access_group_created",
        resource_type="access_group",
        resource_id=str(group.id),
        metadata={"name": group.name},
    )
    db.commit()
    return AccessGroupResponse(id=group.id, name=group.name, slug=group.slug, is_system=False, member_count=0)


@router.post("/groups/{group_id}/members", status_code=status.HTTP_204_NO_CONTENT)
def add_group_members(
    group_id: UUID,
    payload: AccessGroupMembersRequest,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
) -> None:
    group = db.get(AccessGroup, group_id)
    if group is None or group.organization_id != tenant.organization_id:
        raise org_admin_error(code="NOT_FOUND", message="Group not found.", status_code=404)
    for uid in payload.user_ids:
        exists = (
            db.query(AccessGroupMembership)
            .filter(AccessGroupMembership.group_id == group_id, AccessGroupMembership.user_id == uid)
            .first()
        )
        if exists:
            continue
        db.add(
            AccessGroupMembership(
                organization_id=tenant.organization_id,
                group_id=group_id,
                user_id=uid,
            )
        )
    record_audit(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="access_group_members_added",
        resource_type="access_group",
        resource_id=str(group_id),
        metadata={"added_count": len(payload.user_ids)},
    )
    db.commit()


@router.delete("/groups/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_group_member(
    group_id: UUID,
    user_id: UUID,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
) -> None:
    row = (
        db.query(AccessGroupMembership)
        .filter(
            AccessGroupMembership.organization_id == tenant.organization_id,
            AccessGroupMembership.group_id == group_id,
            AccessGroupMembership.user_id == user_id,
        )
        .first()
    )
    if row is None:
        raise org_admin_error(code="NOT_FOUND", message="Membership not found.", status_code=404)
    db.delete(row)
    record_audit(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="access_group_member_removed",
        resource_type="access_group",
        resource_id=str(group_id),
        metadata={"user_id": str(user_id)},
    )
    db.commit()


@router.patch("/documents/{document_id}/visibility", status_code=status.HTTP_204_NO_CONTENT)
def set_document_visibility(
    document_id: UUID,
    payload: DocumentVisibilityRequest,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
) -> None:
    _validate_visibility(payload)
    doc = db.get(ClientDocument, document_id)
    if doc is None or doc.organization_id != tenant.organization_id:
        raise org_admin_error(code="NOT_FOUND", message="Document not found.", status_code=404)
    before = doc.visibility_mode
    doc.visibility_mode = payload.visibility_mode
    doc.visibility_group_ids = list(payload.visibility_group_ids)
    doc.visibility_user_ids = list(payload.visibility_user_ids)
    doc.acl_reviewed = True
    apply_acl_to_evidence_for_document(db, doc)
    record_audit(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="document_visibility_changed",
        resource_type="client_document",
        resource_id=str(doc.id),
        metadata={"before": before, "after": doc.visibility_mode},
    )
    db.commit()


@router.post("/documents/visibility/bulk", status_code=status.HTTP_204_NO_CONTENT)
def bulk_document_visibility(
    payload: BulkDocumentVisibilityRequest,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
) -> None:
    _validate_visibility(payload)
    for doc_id in payload.document_ids:
        doc = db.get(ClientDocument, doc_id)
        if doc is None or doc.organization_id != tenant.organization_id:
            continue
        doc.visibility_mode = payload.visibility_mode
        doc.visibility_group_ids = list(payload.visibility_group_ids)
        doc.visibility_user_ids = list(payload.visibility_user_ids)
        doc.acl_reviewed = True
        apply_acl_to_evidence_for_document(db, doc)
    record_audit(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="documents_visibility_bulk_changed",
        resource_type="client_document",
        resource_id="bulk",
        metadata={"count": len(payload.document_ids), "mode": payload.visibility_mode},
    )
    db.commit()


@router.get("/documents/needs-review/count")
def documents_needing_review(
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
) -> dict[str, int]:
    count = (
        db.query(ClientDocument)
        .filter(
            ClientDocument.organization_id == tenant.organization_id,
            ClientDocument.acl_reviewed.is_(False),
        )
        .count()
    )
    return {"count": count}


@router.post("/preview-as", response_model=PreviewAsResponse)
async def preview_as_user(
    payload: PreviewAsRequest,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
) -> PreviewAsResponse:
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == tenant.organization_id,
            OrganizationMembership.user_id == payload.user_id,
        )
        .first()
    )
    if membership is None:
        raise org_admin_error(code="NOT_FOUND", message="User is not a member of this organization.", status_code=404)
    preview_tenant = TenantContext(
        user_id=payload.user_id,
        organization_id=tenant.organization_id,
        role=Role(membership.role),
        email="",
    )
    access = build_access_context(db, preview_tenant)
    vis_q = evidence_acl_filter(
        db.query(EvidenceItem).filter(EvidenceItem.organization_id == tenant.organization_id),
        access,
        EvidenceItem,
    )
    doc_count = vis_q.with_entities(func.count(func.distinct(EvidenceItem.file_path))).scalar()
    result = await ChatAskService(db).ask(
        organization_id=tenant.organization_id,
        query=payload.query,
        project_id=None,
        user_id=payload.user_id,
        access=access,
    )
    citations = [c.file_name for c in result.get("citations") or []]
    return PreviewAsResponse(
        user_id=payload.user_id,
        query=payload.query,
        accessible_document_count=int(doc_count or 0),
        answer_preview=(result.get("answer") or "")[:4000],
        citation_file_names=citations,
    )
