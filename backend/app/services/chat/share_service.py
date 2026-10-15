import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat_share import ChatConversationShare
from app.models.chat_share_index import ChatShareTokenIndex
from app.models.organization import Organization
from app.services.chat.share_sanitize import sanitize_shared_messages


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ChatShareService:
    def __init__(self, db: Session, *, control_db: Session | None = None) -> None:
        self.db = db
        self.control_db = control_db

    def _assert_sharing_enabled(self, organization_id: uuid.UUID) -> Organization:
        if self.control_db is None:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Share configuration unavailable")
        org = self.control_db.get(Organization, organization_id)
        if org is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
        if not org.chat_shares_enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Conversation sharing is disabled. Your organization admin can enable it in the admin console.",
            )
        return org

    def create_or_update_share(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        client_conversation_id: str,
        title: str,
        messages: list[dict],
    ) -> ChatConversationShare:
        org = self._assert_sharing_enabled(organization_id)
        client_conversation_id = client_conversation_id.strip()
        if not client_conversation_id or len(client_conversation_id) > 64:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid conversation reference")

        ttl_days = max(1, min(int(org.chat_share_ttl_days or 7), 90))
        expires_at = _utcnow() + timedelta(days=ttl_days)
        safe_messages = sanitize_shared_messages(messages)

        existing = self.db.scalar(
            select(ChatConversationShare).where(
                ChatConversationShare.organization_id == organization_id,
                ChatConversationShare.created_by_user_id == user_id,
                ChatConversationShare.client_conversation_id == client_conversation_id,
                ChatConversationShare.revoked_at.is_(None),
            )
        )
        if existing:
            existing.title = (title or "Shared conversation")[:200]
            existing.messages = safe_messages
            existing.expires_at = expires_at
            existing.updated_at = _utcnow()
            self._upsert_index(existing.share_token, organization_id, expires_at)
            self.db.flush()
            return existing

        share = ChatConversationShare(
            share_token=secrets.token_urlsafe(32),
            organization_id=organization_id,
            created_by_user_id=user_id,
            client_conversation_id=client_conversation_id,
            title=(title or "Shared conversation")[:200],
            messages=safe_messages,
            expires_at=expires_at,
        )
        self.db.add(share)
        self.db.flush()
        self._upsert_index(share.share_token, organization_id, expires_at)
        return share

    def _upsert_index(self, token: str, organization_id: uuid.UUID, expires_at: datetime) -> None:
        if self.control_db is None:
            return
        row = self.control_db.get(ChatShareTokenIndex, token)
        if row is None:
            row = ChatShareTokenIndex(
                share_token=token,
                organization_id=organization_id,
                expires_at=expires_at,
            )
            self.control_db.add(row)
        else:
            row.organization_id = organization_id
            row.expires_at = expires_at
            row.revoked_at = None
        self.control_db.flush()

    def _is_expired(self, share: ChatConversationShare) -> bool:
        if share.expires_at is None:
            return False
        exp = share.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        return exp < _utcnow()

    def get_share_for_tenant(
        self,
        *,
        token: str,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        is_org_admin: bool = False,
        allow_public: bool = False,
    ) -> ChatConversationShare:
        share = self._load_active_share(token=token, organization_id=organization_id)
        if not allow_public:
            if user_id is None:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this share link")
            if share.created_by_user_id != user_id and not is_org_admin:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this share link")
        return share

    def _load_active_share(self, *, token: str, organization_id: uuid.UUID) -> ChatConversationShare:
        share = self.db.scalar(
            select(ChatConversationShare).where(
                ChatConversationShare.share_token == token,
                ChatConversationShare.organization_id == organization_id,
                ChatConversationShare.revoked_at.is_(None),
            )
        )
        if not share or self._is_expired(share):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found or expired")
        share.messages = sanitize_shared_messages(share.messages or [])
        return share

    def revoke_share(
        self,
        *,
        token: str,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        is_org_admin: bool,
    ) -> None:
        share = self.db.scalar(
            select(ChatConversationShare).where(
                ChatConversationShare.share_token == token,
                ChatConversationShare.organization_id == organization_id,
                ChatConversationShare.revoked_at.is_(None),
            )
        )
        if not share:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found")
        if share.created_by_user_id != user_id and not is_org_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to revoke this link")
        share.revoked_at = _utcnow()
        if self.control_db is not None:
            index = self.control_db.get(ChatShareTokenIndex, token)
            if index is not None:
                index.revoked_at = share.revoked_at
                self.control_db.flush()
        self.db.flush()
