import asyncio
import logging
from uuid import UUID

from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.evidence import EvidenceItem
from app.services.access_control.context import UserAccessContext
from app.services.ingestion.embedding_health import reembed_stale_chunks, warn_on_stale_embeddings
from app.services.llm.factory import get_llm_provider
from app.services.llm.guardrails import clamp_question
from app.services.retrieval.debug_log import log_rag_event
from app.services.retrieval.keywords import extract_keyword_terms
from app.services.retrieval.scope import count_org_evidence_chunks

logger = logging.getLogger("aqrem.rag")


class RetrievalService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _keyword_query(
        self,
        *,
        organization_id: UUID,
        limit: int,
        query: str,
    ) -> list[EvidenceItem]:
        """Keyword fallback. The only filter is the organization."""
        q = self.db.query(EvidenceItem).filter(EvidenceItem.organization_id == organization_id)

        terms = extract_keyword_terms(query)
        if terms:
            like_clauses = []
            for term in terms:
                pat = f"%{term}%"
                like_clauses.append(EvidenceItem.content.ilike(pat))
                like_clauses.append(EvidenceItem.file_name.ilike(pat))
                like_clauses.append(EvidenceItem.file_path.ilike(pat))
            q = q.filter(or_(*like_clauses))
        else:
            q = q.filter(
                EvidenceItem.search_vector.op("@@")(func.plainto_tsquery("english", query))
            )

        return q.order_by(func.length(EvidenceItem.content).desc()).limit(limit).all()

    async def retrieve(
        self,
        *,
        organization_id: UUID,
        query: str,
        project_id: UUID | None = None,
        source_id: UUID | None = None,
        limit: int = 8,
        access: UserAccessContext | None = None,
    ) -> list[EvidenceItem]:
        settings = get_settings()
        limit = min(max(limit, 1), settings.llm_max_retrieval_results)
        safe_query = clamp_question(query)
        llm = get_llm_provider(organization_id)
        if llm.provider_name in {"mock", "local"}:
            # Cheap deterministic embeddings: heal stale vectors inline (dev/tests only).
            await reembed_stale_chunks(self.db, organization_id)
        else:
            warn_on_stale_embeddings(self.db, organization_id, llm.embedding_model_id, settings.embedding_dimensions)
        org_chunk_count = count_org_evidence_chunks(
            self.db, organization_id=organization_id, project_id=None
        )
        log_rag_event(
            "retrieve_start",
            organization_id=organization_id,
            ignored_project_id=project_id,
            ignored_source_id=source_id,
            filters=["organization_id"],
            org_chunk_count=org_chunk_count,
            query=safe_query,
            limit=limit,
            user_id=getattr(access, "user_id", None),
            is_org_admin=getattr(access, "is_org_admin", None),
        )

        query_embedding = (await llm.embed([safe_query]))[0]
        if len(query_embedding) != settings.embedding_dimensions:
            logger.warning(
                "Query embedding size %s does not match EMBEDDING_DIMENSIONS %s; falling back to keyword search",
                len(query_embedding),
                settings.embedding_dimensions,
            )
            return self._finish(
                organization_id=organization_id,
                question=safe_query,
                items=self._keyword_query(
                    organization_id=organization_id,
                    limit=limit,
                    query=safe_query,
                ),
                scores=[],
                method="keyword_dimension_mismatch",
            )
        embedding_literal = "[" + ",".join(str(x) for x in query_embedding) + "]"

        vector_sql = text(
            """
            SELECT id, file_name, (
                CASE WHEN COALESCE(metadata->>'embedding_model', '') = :model
                     THEN COALESCE(1 - (embedding <=> CAST(:embedding AS vector)), 0)
                     ELSE 0 END * 0.6 +
                COALESCE(ts_rank(search_vector, plainto_tsquery('english', :query)), 0) * 0.4
            ) AS score
            FROM evidence_items
            WHERE organization_id = :org_id AND embedding IS NOT NULL
            ORDER BY score DESC
            LIMIT :limit
            """
        )
        params = {
            "org_id": str(organization_id),
            "limit": limit,
            "query": safe_query,
            "embedding": embedding_literal,
            "model": llm.embedding_model_id,
        }
        try:
            with self.db.begin_nested():
                rows = self.db.execute(vector_sql, params).fetchall()
        except Exception:
            logger.exception(
                "Vector search failed org=%s; falling back to keyword search",
                organization_id,
            )
            rows = []

        if rows:
            ids = [row[0] for row in rows]
            top_scores = [
                {
                    "id": str(row[0]),
                    "file_name": row[1],
                    "score": float(row[2]) if row[2] is not None else 0.0,
                }
                for row in rows[:8]
            ]
            items = self.db.query(EvidenceItem).filter(EvidenceItem.id.in_(ids)).all()
            order = {item_id: idx for idx, item_id in enumerate(ids)}
            ordered = sorted(items, key=lambda i: order.get(i.id, 999))
            ordered = [i for i in ordered if i.organization_id == organization_id]
            return self._finish(
                organization_id=organization_id,
                question=safe_query,
                items=ordered,
                scores=top_scores,
                method="vector",
            )

        keyword_items = self._keyword_query(
            organization_id=organization_id,
            limit=limit,
            query=safe_query,
        )
        keyword_scores = [
            {"id": str(item.id), "file_name": item.file_name, "score": None}
            for item in keyword_items[:8]
        ]
        return self._finish(
            organization_id=organization_id,
            question=safe_query,
            items=keyword_items,
            scores=keyword_scores,
            method="keyword",
        )

    def _finish(
        self,
        *,
        organization_id: UUID,
        question: str,
        items: list[EvidenceItem],
        scores: list[dict],
        method: str,
    ) -> list[EvidenceItem]:
        logger.info(
            "RAG retrieval org=%s question=%r filters=organization_id method=%s chunks=%s scores=%s",
            organization_id,
            question[:180],
            method,
            len(items),
            scores,
        )
        log_rag_event(
            "retrieve_result",
            organization_id=organization_id,
            filters=["organization_id"],
            method=method,
            chunk_count=len(items),
            scores=scores,
            files=[item.file_name for item in items[:8]],
        )
        return items


def retrieve_sync(db: Session, **kwargs) -> list[EvidenceItem]:
    return asyncio.get_event_loop().run_until_complete(RetrievalService(db).retrieve(**kwargs))
