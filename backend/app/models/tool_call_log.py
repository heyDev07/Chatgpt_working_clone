import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class ToolCallLog(UUIDPrimaryKeyMixin, Base):
    """Append-only audit trail of every tool invocation - no updated_at/TimestampMixin since
    a log entry is never mutated after it's written."""

    __tablename__ = "tool_call_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    arguments: Mapped[dict] = mapped_column(JSONB, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
