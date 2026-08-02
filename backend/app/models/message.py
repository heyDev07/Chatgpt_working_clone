import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.message_attachment import MessageAttachment


class Message(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user','assistant','system')", name="ck_messages_role"),
        CheckConstraint("feedback IN ('up','down')", name="ck_messages_feedback"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    finish_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Which specialized persona (see app/agents/definitions.py) generated this assistant reply -
    # null for user/system messages and for any assistant reply predating this feature.
    agent: Mapped[str | None] = mapped_column(String(30), nullable=True)
    feedback: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Computed (RAG document matches, or Deep Research's web sources) but historically thrown
    # away once the SSE "done" event was sent - this is what lets a cited reply survive a reload.
    # Deliberately loose (list[dict], not a fixed schema): RAG citations are
    # {filename,document_id,score}, Deep Research's are {title,url,snippet} - genuinely different
    # shapes that don't need unifying, both rendered by the same frontend CitationList component.
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    attachments: Mapped[list["MessageAttachment"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )
