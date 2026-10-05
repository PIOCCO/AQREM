import hashlib
import uuid
from dataclasses import dataclass

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
from app.services.library.invalidate import mark_entries_stale_for_evidence
from app.services.llm.factory import get_llm_provider


@dataclass
class FilePayload:
    relative_path: str
    data: bytes
    repository: str | None = None
    branch: str | None = None
    commit_hash: str | None = None


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def index_files(
    db: Session,
    *,
    source: Source,
    job: SourceSyncJob,
    files: list[FilePayload],
) -> dict:
    db.refresh(source)
    path_spec = build_pathspec(db, source.organization_id, source.project_id)
    llm = get_llm_provider()
    indexed = 0
    skipped = 0
    updated = 0

    source.status = SourceStatus.INDEXING.value
    db.flush()

    for file in files:
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
        chunks = chunk_text(text_content)
        if not chunks:
            continue

        chunk_texts = [c.content for c in chunks]
        embeddings = await llm.embed(chunk_texts)

        for chunk, embedding in zip(chunks, embeddings, strict=False):
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
                indexed += 1
                continue

            if existing and existing.content_hash != c_hash:
                mark_entries_stale_for_evidence(db, existing.id)
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
                db.execute(
                    text(
                        "UPDATE evidence_items SET search_vector = to_tsvector('english', :content) WHERE id = :id"
                    ),
                    {"content": chunk.content, "id": str(existing.id)},
                )
                updated += 1
                indexed += 1
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
                embedding=embedding,
            )
            db.add(item)
            db.flush()
            db.execute(
                text("UPDATE evidence_items SET search_vector = to_tsvector('english', :content) WHERE id = :id"),
                {"content": chunk.content, "id": str(item.id)},
            )
            indexed += 1

    source.status = SourceStatus.READY.value
    job.status = SyncJobStatus.COMPLETED.value
    job.stats = {"indexed_chunks": indexed, "skipped_files": skipped, "updated_chunks": updated}
    db.flush()
    return job.stats
