"""Chunk embedding health, re-index, and per-document search readiness."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.client_admin import ClientDocument
from app.models.evidence import EvidenceItem
from app.services.llm.errors import EmbeddingDimensionMismatchError
from app.services.llm.factory import get_llm_provider

logger = logging.getLogger("aqrem.rag")

_BATCH = 16


def stamp_embedding(item: EvidenceItem, vector: list[float], model_id: str, dimensions: int) -> None:
    item.embedding = list(vector)
    meta = dict(item.item_metadata or {})
    meta["embedding_model"] = model_id
    meta["embedding_dimensions"] = dimensions
    item.item_metadata = meta


def embedding_is_current(item: EvidenceItem, model_id: str, dimensions: int) -> bool:
    vector = item.embedding
    if vector is None:
        return False
    try:
        length = len(vector)
    except TypeError:
        return False
    if length != dimensions:
        return False
    meta = item.item_metadata or {}
    return meta.get("embedding_model") == model_id and int(meta.get("embedding_dimensions") or 0) == dimensions


def count_stale_chunks(db: Session, organization_id: UUID, model_id: str, dimensions: int) -> int:
    """Chunks whose stored embedding was built with another deployment/size (or is missing)."""
    row = db.execute(
        text(
            """
            SELECT COUNT(*)::int FROM evidence_items
            WHERE organization_id = :org
              AND (
                embedding IS NULL
                OR COALESCE(metadata->>'embedding_model', '') <> :model
                OR COALESCE(metadata->>'embedding_dimensions', '') <> :dim_text
              )
            """
        ),
        {"org": str(organization_id), "model": model_id, "dim_text": str(dimensions)},
    ).scalar()
    return int(row or 0)


def warn_on_stale_embeddings(db: Session, organization_id: UUID, model_id: str, dimensions: int) -> int:
    try:
        stale = count_stale_chunks(db, organization_id, model_id, dimensions)
    except Exception:  # noqa: BLE001
        logger.exception("Could not count stale embeddings org=%s", organization_id)
        return 0
    if stale:
        logger.warning(
            "EMBEDDING MISMATCH org=%s: %s chunks were indexed with a different embedding deployment/size "
            "than the current config (%s). They are only keyword-searchable until an admin runs "
            "'Re-index all documents' (Documents page or POST /api/v1/org-admin/documents/reindex-all).",
            organization_id,
            stale,
            model_id,
        )
    return stale


def document_embedding_mismatch(doc: ClientDocument, model_id: str, dimensions: int) -> bool:
    """True when an indexed document was embedded with another deployment or vector size."""
    if doc.status != "indexed":
        return False
    stored_model = getattr(doc, "embedding_model", None)
    stored_dim = getattr(doc, "embedding_dimensions", None)
    if not stored_model and not stored_dim:
        return False  # indexed before this was tracked; chunk-level health covers it
    return stored_model != model_id or int(stored_dim or 0) != dimensions


async def reembed_stale_chunks(db: Session, organization_id: UUID) -> int:
    """Re-embed chunks in this organization that are missing a vector or were built with another model."""
    settings = get_settings()
    llm = get_llm_provider(organization_id)
    model_id = llm.embedding_model_id
    dim = settings.embedding_dimensions
    rows = db.execute(
        text(
            """
            SELECT id
            FROM evidence_items
            WHERE organization_id = :org
              AND (
                embedding IS NULL
                OR vector_dims(embedding) <> :dim
                OR COALESCE(metadata->>'embedding_model', '') <> :model
                OR COALESCE(metadata->>'embedding_dimensions', '') <> :dim_text
              )
            """
        ),
        {
            "org": str(organization_id),
            "dim": dim,
            "model": model_id,
            "dim_text": str(dim),
        },
    ).fetchall()
    if not rows:
        return 0
    ids = [row[0] for row in rows]
    items = db.query(EvidenceItem).filter(EvidenceItem.id.in_(ids)).all()
    items = [item for item in items if (item.content or "").strip()]
    updated = 0
    for offset in range(0, len(items), _BATCH):
        batch = items[offset : offset + _BATCH]
        vectors = await llm.embed([item.content for item in batch])
        if len(vectors) != len(batch):
            raise RuntimeError(
                f"Embedding provider returned {len(vectors)} vectors for {len(batch)} chunks."
            )
        for item, vector in zip(batch, vectors, strict=True):
            if not vector or len(vector) != dim:
                raise EmbeddingDimensionMismatchError(expected=dim, actual=len(vector or []))
            stamp_embedding(item, vector, model_id, dim)
            updated += 1
        db.flush()
    logger.info(
        "Re-indexed %s chunks missing or stale embeddings org=%s embedding_model=%s dimensions=%s",
        updated,
        organization_id,
        model_id,
        dim,
    )
    return updated


def document_search_health(db: Session, doc: ClientDocument) -> dict:
    """Chunk count, embedding coverage, vector size, and leftover project/access tags."""
    settings = get_settings()
    llm = get_llm_provider(doc.organization_id)
    model_id = llm.embedding_model_id
    dim = settings.embedding_dimensions
    if doc.source_id is None:
        return {
            "chunks_stored": 0,
            "chunks_with_embedding": 0,
            "embedding_dimensions": None,
            "embedding_model": model_id,
            "search_ready": False,
            "organization_id": doc.organization_id,
            "leftover_project_ids": [],
            "leftover_visibility_modes": [],
        }
    row = db.execute(
        text(
            """
            SELECT
              COUNT(*)::int AS stored,
              COUNT(embedding)::int AS embedded,
              COUNT(*) FILTER (
                WHERE embedding IS NOT NULL
                  AND vector_dims(embedding) = :dim
                  AND COALESCE(metadata->>'embedding_model', '') = :model
              )::int AS current_embeddings,
              MAX(vector_dims(embedding)) AS vector_size,
              COALESCE(
                ARRAY_AGG(DISTINCT project_id::text) FILTER (WHERE project_id IS NOT NULL),
                '{}'
              ) AS project_ids,
              COALESCE(
                ARRAY_AGG(DISTINCT visibility_mode) FILTER (WHERE visibility_mode IS NOT NULL),
                '{}'
              ) AS visibility_modes
            FROM evidence_items
            WHERE organization_id = :org
              AND source_id = :source
              AND file_name = :file_name
            """
        ),
        {
            "org": str(doc.organization_id),
            "source": str(doc.source_id),
            "file_name": doc.file_name,
            "dim": dim,
            "model": model_id,
        },
    ).one()
    stored = int(row.stored or 0)
    embedded = int(row.embedded or 0)
    current = int(row.current_embeddings or 0)
    projects = [str(value) for value in (row.project_ids or []) if value]
    visibility = [str(value) for value in (row.visibility_modes or []) if value]
    return {
        "chunks_stored": stored,
        "chunks_with_embedding": embedded,
        "embedding_dimensions": int(row.vector_size) if row.vector_size is not None else None,
        "embedding_model": model_id,
        "search_ready": stored > 0 and current == stored,
        "organization_id": doc.organization_id,
        "leftover_project_ids": projects,
        "leftover_visibility_modes": visibility,
    }


def apply_index_truth(doc: ClientDocument, health: dict) -> None:
    """Indexed is true only when every stored chunk has a current embedding."""
    if doc.status in {"queued", "uploading", "indexing"} and not health["search_ready"]:
        return
    if health["search_ready"]:
        doc.status = "indexed"
        doc.embedding_model = health.get("embedding_model")
        doc.embedding_dimensions = int(health.get("embedding_dimensions") or 0) or None
        doc.index_stage = "indexed"
        doc.index_progress = 100
        doc.indexed_chunk_count = int(health["chunks_with_embedding"])
        doc.failure_reason = None
        return
    if doc.status == "indexed" or doc.index_stage == "indexed":
        doc.status = "failed"
        doc.index_stage = "failed"
        doc.indexed_chunk_count = int(health["chunks_with_embedding"])
        if health["chunks_stored"] <= 0:
            doc.failure_reason = "Indexing did not store any chunks."
        else:
            doc.failure_reason = "Indexing did not store embeddings for every chunk."
