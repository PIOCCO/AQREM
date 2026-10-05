from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_context
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.answer_library import AnswerLibraryEntry, AnswerLibraryEvidenceLink
from app.schemas.answer_library import (
    AnswerLibraryEntryResponse,
    AnswerLibrarySearchRequest,
    LibraryEvidenceRef,
)
from app.services.library.service import AnswerLibraryService
from app.services.library.validation import validate_library_evidence

router = APIRouter()


def _entry_response(db: Session, entry: AnswerLibraryEntry) -> AnswerLibraryEntryResponse:
    links = (
        db.query(AnswerLibraryEvidenceLink)
        .filter(AnswerLibraryEvidenceLink.library_entry_id == entry.id)
        .all()
    )
    evidence = [
        LibraryEvidenceRef(
            evidence_item_id=link.evidence_item_id,
            file_path=link.file_path,
            snapshot_content_hash=link.snapshot_content_hash,
            evidence_strength=link.evidence_strength,
        )
        for link in links
    ]
    return AnswerLibraryEntryResponse(
        id=entry.id,
        organization_id=entry.organization_id,
        project_id=entry.project_id,
        scope=entry.scope,
        question_text=entry.question_text,
        normalized_question=entry.normalized_question,
        answer_text=entry.answer_text,
        status=entry.status,
        version=entry.version,
        reuse_count=entry.reuse_count,
        approved_at=entry.approved_at,
        evidence=evidence,
    )


@router.get("", response_model=list[AnswerLibraryEntryResponse])
def list_library_entries(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    project_id: UUID | None = Query(default=None),
    query: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AnswerLibraryEntryResponse]:
    entries = AnswerLibraryService(db).search_entries(
        organization_id=tenant.organization_id,
        project_id=project_id,
        query=query,
        limit=limit,
    )
    return [_entry_response(db, entry) for entry in entries]


@router.post("/search", response_model=list[AnswerLibraryEntryResponse])
def search_library(
    payload: AnswerLibrarySearchRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> list[AnswerLibraryEntryResponse]:
    entries = AnswerLibraryService(db).search_entries(
        organization_id=tenant.organization_id,
        query=payload.query,
        project_id=payload.project_id,
        limit=payload.limit,
    )
    return [_entry_response(db, entry) for entry in entries]


@router.get("/{entry_id}", response_model=AnswerLibraryEntryResponse)
def get_library_entry(
    entry_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> AnswerLibraryEntryResponse:
    entry = db.get(AnswerLibraryEntry, entry_id)
    if entry is None or entry.organization_id != tenant.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library entry not found")
    return _entry_response(db, entry)


@router.get("/{entry_id}/validation")
def validate_entry(
    entry_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    entry = db.get(AnswerLibraryEntry, entry_id)
    if entry is None or entry.organization_id != tenant.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library entry not found")
    result = validate_library_evidence(db, entry)
    return {
        "valid": result.valid,
        "missing_count": result.missing_count,
        "changed_count": result.changed_count,
        "checked_count": result.checked_count,
        "details": result.details,
    }
