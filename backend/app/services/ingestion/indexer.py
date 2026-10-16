import hashlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.enums import SourceStatus, SyncJobStatus
from app.models.evidence import EvidenceItem, EvidenceItemVersion
from app.models.source import Source, SourceSyncJob
from app.services.ingestion.chunking import chunk_text
from app.services.ingestion.code_metadata import detect_language, extract_symbols
from app.services.ingestion.ignore import build_pathspec, should_ignore
from app.services.ingestion.parsers import parse_bytes
from app.services.ingestion.strength import classify_evidence_strength
from app.services.access_control.document_acl import resolve_document_acl
from app.services.ingestion.chunking import page_break_lines, page_for_line
from app.services.ingestion.embedding_health import embedding_is_current, stamp_embedding
from app.services.library.invalidate import mark_evidence_changed
from app.core.config import get_settings
from app.services.llm.errors import EmbeddingDimensionMismatchError
from app.services.llm.factory import get_llm_provider


def _apply_chunk_visibility(
    db: Session,
    *,
    source: Source,
    file_name: str,
    item: EvidenceItem,
) -> None:
    mode, group_ids, user_ids = resolve_document_acl(
        db,
        organization_id=source.organization_id,
        source_id=source.id,
        file_name=file_name,
    )
    item.visibility_mode = mode
    item.visibility_group_ids = group_ids
    item.visibility_user_ids = user_ids


@dataclass
class FilePayload:
    relative_path: str
    data: bytes
    repository: str | None = None
    branch: str | None = None
    commit_hash: str | None = None


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


ProgressFn = Callable[[str, int, int | None], None]



def _stamp_page(item: EvidenceItem, breaks: list[int], line_start: int | None, content_type: str) -> None:
    if content_type != "application/pdf":
        return
    page = page_for_line(breaks, line_start)
    if page is None:
        return
    meta = dict(item.item_metadata or {})
    if meta.get("page") != page:
        meta["page"] = page
        item.item_metadata = meta

async def index_files(
    db: Session,
    *,
    source: Source,
    job: SourceSyncJob,
    files: list[FilePayload],
    on_progress: ProgressFn | None = None,
) -> dict:
    db.refresh(source)
    path_spec = build_pathspec(db, source.organization_id, source.project_id)
    llm = get_llm_provider(source.organization_id)
    expected_dim = get_settings().embedding_dimensions
    model_id = llm.embedding_model_id
    indexed = 0
    embedded = 0
    skipped = 0
    updated = 0

    source.status = SourceStatus.INDEXING.value
    db.flush()

    def report(stage: str, processed: int, total: int | None) -> None:
        job.progress_updated_at = datetime.now(UTC)
        if on_progress:
            on_progress(stage, processed, total)

    report("parsing", 0, len(files) if files else None)
    file_index = 0

    for file in files:
        file_index += 1
        report("parsing", file_index, len(files))
        rel = file.relative_path.replace("\\", "/")
        if should_ignore(path_spec, rel):
            skipped += 1
            continue

        try:
            text_content, content_type = parse_bytes(rel, file.data)
        except Exception:
            skipped += 1
            continue

        if not text_content.strip():
            skipped += 1
            continue

        language = detect_language(rel)
        symbols = extract_symbols(text_content, language)
        report("chunking", file_index, len(files))
        chunks = chunk_text(text_content)
        if not chunks:
            continue
        breaks = page_break_lines(text_content) if content_type == "application/pdf" else []
        for chunk in chunks:
            chunk.content = chunk.content.replace("\f", "").strip() or chunk.content

        chunk_texts = [c.content for c in chunks]
        report("embedding", 0, len(chunks))
        embeddings = await llm.embed(chunk_texts)
        report("embedding", len(chunks), len(chunks))
        if len(embeddings) != len(chunks):
            raise RuntimeError(
                f"Embedding provider returned {len(embeddings)} vectors for {len(chunks)} chunks."
            )
        for vec in embeddings:
            if not vec or len(vec) != expected_dim:
                raise EmbeddingDimensionMismatchError(
                    expected=expected_dim,
                    actual=len(vec or []),
                )

        written = 0
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            c_hash = content_hash(chunk.content)
            existing = (
                db.query(EvidenceItem)
                .filter(
                    EvidenceItem.source_id == source.id,
                    EvidenceItem.file_path == rel,
                    EvidenceItem.chunk_index == chunk.chunk_index,
                )
                .first()
            )
            symbol = next(
                (s for s in symbols if s.line_start and chunk.line_start and s.line_start <= chunk.line_start),
                None,
            )
            strength = classify_evidence_strength(rel, content_type, source.source_type)

            if existing and existing.content_hash == c_hash:
                _apply_chunk_visibility(db, source=source, file_name=rel.split("/")[-1], item=existing)
                if not embedding_is_current(existing, model_id, expected_dim):
                    stamp_embedding(existing, embedding, model_id, expected_dim)
                _stamp_page(existing, breaks, chunk.line_start, content_type)
                indexed += 1
                embedded += 1
                continue

            if existing and existing.content_hash != c_hash:
                mark_evidence_changed(
                    db,
                    organization_id=source.organization_id,
                    evidence_item_id=existing.id,
                    file_path=rel,
                    snapshot_content_hash=existing.content_hash,
                    current_content_hash=c_hash,
                    previous_commit_hash=existing.commit_hash,
                    current_commit_hash=file.commit_hash,
                    previous_content_excerpt=existing.content[:500],
                    current_content_excerpt=chunk.content[:500],
                    evidence_strength=existing.evidence_strength or strength,
                )
                db.add(
                    EvidenceItemVersion(
                        evidence_item_id=existing.id,
                        organization_id=source.organization_id,
                        commit_hash=file.commit_hash,
                        content_hash=existing.content_hash,
                        file_path=rel,
                        line_start=existing.line_start,
                        line_end=existing.line_end,
                    )
                )
                existing.content = chunk.content
                existing.content_hash = c_hash
                existing.embedding = embedding
                existing.commit_hash = file.commit_hash
                existing.line_start = chunk.line_start
                existing.line_end = chunk.line_end
                existing.symbol_name = symbol.name if symbol else None
                existing.symbol_kind = symbol.kind if symbol else None
                existing.evidence_strength = strength
                stamp_embedding(existing, embedding, model_id, expected_dim)
                _stamp_page(existing, breaks, chunk.line_start, content_type)
                _apply_chunk_visibility(db, source=source, file_name=rel.split("/")[-1], item=existing)
                db.execute(
                    text(
                        "UPDATE evidence_items SET search_vector = to_tsvector('english', :content) WHERE id = :id"
                    ),
                    {"content": chunk.content, "id": str(existing.id)},
                )
                updated += 1
                indexed += 1
                embedded += 1
                continue

            item = EvidenceItem(
                id=uuid.uuid4(),
                organization_id=source.organization_id,
                project_id=source.project_id,
                source_id=source.id,
                source_type=source.source_type,
                scope=source.scope,
                file_name=rel.split("/")[-1],
                file_path=rel,
                content=chunk.content,
                content_type=content_type,
                language=language,
                repository=file.repository,
                branch=file.branch,
                commit_hash=file.commit_hash,
                line_start=chunk.line_start,
                line_end=chunk.line_end,
                symbol_name=symbol.name if symbol else None,
                symbol_kind=symbol.kind if symbol else None,
                chunk_index=chunk.chunk_index,
                content_hash=c_hash,
                evidence_strength=strength,
            )
            stamp_embedding(item, embedding, model_id, expected_dim)
            _stamp_page(item, breaks, chunk.line_start, content_type)
            db.add(item)
            db.flush()
            _apply_chunk_visibility(db, source=source, file_name=rel.split("/")[-1], item=item)
            db.execute(
                text("UPDATE evidence_items SET search_vector = to_tsvector('english', :content) WHERE id = :id"),
                {"content": chunk.content, "id": str(item.id)},
            )
            indexed += 1
            embedded += 1
            written += 1
            report("writing", written, len(chunks))

    source.status = SourceStatus.READY.value
    job.status = SyncJobStatus.COMPLETED.value
    job.stats = {
        "indexed_chunks": indexed,
        "embedded_chunks": embedded,
        "skipped_files": skipped,
        "updated_chunks": updated,
        "embedding_model": model_id,
        "embedding_dimensions": expected_dim,
    }
    db.flush()
    return job.stats
