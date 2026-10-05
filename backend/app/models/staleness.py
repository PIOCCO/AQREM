import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnswerStalenessEvent(Base):
    __tablename__ = "answer_staleness_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    answer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("answers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    file_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    snapshot_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    current_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_commit_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_commit_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous_content_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_content_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_strength: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open", index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
