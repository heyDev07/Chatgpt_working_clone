import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.message import Message


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New Conversation")
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="openai")
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Model controls. Null means "use the provider's default" for that field.
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    top_p: Mapped[float | None] = mapped_column(Float, nullable=True)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )
