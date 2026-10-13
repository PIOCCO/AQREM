import secrets
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat_share import ChatConversationShare


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ChatShareService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_or_update_share(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        client_conversation_id: str,
        title: str,
        messages: list[dict],
    ) -> ChatConversationShare:
        client_conversation_id = client_conversation_id.strip()
        if not client_conversation_id or len(client_conversation_id) > 64:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid conversation reference")

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
            existing.messages = messages
            existing.updated_at = _utcnow()
            self.db.flush()
            return existing

        share = ChatConversationShare(
            share_token=secrets.token_urlsafe(32),
            organization_id=organization_id,
            created_by_user_id=user_id,
            client_conversation_id=client_conversation_id,
            title=(title or "Shared conversation")[:200],
            messages=messages,
        )
        self.db.add(share)
        self.db.flush()
        return share

    def get_share_for_tenant(self, *, token: str, organization_id: uuid.UUID) -> ChatConversationShare:
        share = self.db.scalar(
            select(ChatConversationShare).where(
                ChatConversationShare.share_token == token,
                ChatConversationShare.organization_id == organization_id,
                ChatConversationShare.revoked_at.is_(None),
            )
        )
        if not share:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found or expired")
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
        self.db.flush()
