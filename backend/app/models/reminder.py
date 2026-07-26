import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Reminder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reminders"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Nullable - a reminder created via the create_reminder tool mid-conversation is linked back
    # to it (so "what conversation was this reminder from?" has an answer), but the API also
    # allows creating one with no conversation context at all.
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    remind_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    # Set once the scheduled APScheduler job actually fires - not "read/unread" (the frontend
    # decides that from whether it's shown the toast yet), this is specifically "did the job run."
    is_delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
