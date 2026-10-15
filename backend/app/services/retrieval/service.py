import asyncio
from uuid import UUID

from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.evidence import EvidenceItem
from app.services.access_control.context import UserAccessContext
from app.services.access_control.policy import acl_bind_params, acl_sql_fragment, evidence_acl_filter
from app.services.llm.factory import get_llm_provider
from app.services.llm.guardrails import clamp_question
from app.services.retrieval.debug_log import log_rag_event
from app.services.retrieval.keywords import extract_keyword_terms
from app.services.retrieval.scope import apply_evidence_scope_filter, count_org_evidence_chunks


class RetrievalService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _keyword_query(
        self,
        *,
        organization_id: UUID,
        project_id: UUID | None,
        source_id: UUID | None,
        access: UserAccessContext | None,
        limit: int,
        query: str,
    ) -> list[EvidenceItem]:
        q = self.db.query(EvidenceItem).filter(EvidenceItem.organization_id == organization_id)
        q = apply_evidence_scope_filter(q, project_id)
        if source_id:
            q = q.filter(EvidenceItem.source_id == source_id)
        if access is not None:
            q = evidence_acl_filter(q, access, EvidenceItem)

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
        org_chunk_count = count_org_evidence_chunks(
            self.db, organization_id=organization_id, project_id=project_id
        )
        log_rag_event(
            "retrieve_start",
            organization_id=organization_id,
            project_id=project_id,
            org_chunk_count=org_chunk_count,
            query=safe_query,
            limit=limit,
            user_id=getattr(access, "user_id", None),
            is_org_admin=getattr(access, "is_org_admin", None),
        )

        llm = get_llm_provider(organization_id)
        query_embedding = (await llm.embed([safe_query]))[0]
        embedding_literal = "[" + ",".join(str(x) for x in query_embedding) + "]"

        scope_filter = "organization_id = :org_id"
        params: dict = {"org_id": str(organization_id), "limit": limit, "query": safe_query}

        if project_id:
            scope_filter += (
                " AND (project_id = :project_id OR "
                "(project_id IS NULL AND scope = 'organization'))"
            )
            params["project_id"] = str(project_id)
        if source_id:
            scope_filter += " AND source_id = :source_id"
            params["source_id"] = str(source_id)

        if access is not None:
            scope_filter += f" AND ({acl_sql_fragment().strip()})"
            params.update(acl_bind_params(access))

        vector_sql = text(
            f"""
            SELECT id, file_name, (
                COALESCE(1 - (embedding <=> CAST(:embedding AS vector)), 0) * 0.6 +
                COALESCE(ts_rank(search_vector, plainto_tsquery('english', :query)), 0) * 0.4
            ) AS score
            FROM evidence_items
            WHERE {scope_filter} AND embedding IS NOT NULL
            ORDER BY score DESC
            LIMIT :limit
            """
        )
        params["embedding"] = embedding_literal
        rows = self.db.execute(vector_sql, params).fetchall()
        if rows:
            ids = [row[0] for row in rows]
            top_scores = [
                {"file_name": row[1], "score": float(row[2]) if row[2] is not None else 0.0}
                for row in rows[:5]
            ]
            log_rag_event(
                "vector_hits",
                organization_id=organization_id,
                project_id=project_id,
                hit_count=len(rows),
                top_scores=top_scores,
            )
            items = self.db.query(EvidenceItem).filter(EvidenceItem.id.in_(ids)).all()
            order = {item_id: idx for idx, item_id in enumerate(ids)}
            ordered = sorted(items, key=lambda i: order.get(i.id, 999))
            return [i for i in ordered if i.organization_id == organization_id]

        log_rag_event(
            "vector_miss_keyword_fallback",
            organization_id=organization_id,
            project_id=project_id,
            keyword_terms=extract_keyword_terms(safe_query),
        )
        return self._keyword_query(
            organization_id=organization_id,
            project_id=project_id,
            source_id=source_id,
            access=access,
            limit=limit,
            query=safe_query,
        )


def retrieve_sync(db: Session, **kwargs) -> list[EvidenceItem]:
    return asyncio.get_event_loop().run_until_complete(RetrievalService(db).retrieve(**kwargs))
