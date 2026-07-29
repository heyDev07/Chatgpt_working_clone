import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LinkedInCredential(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "linkedin_credentials"

    # One LinkedIn connection per app user, same reasoning as GoogleCredential.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # Same plaintext-for-now gap as GoogleCredential.access_token - see that model's comment.
    # No refresh_token: LinkedIn's OpenID Connect product (the only self-serve one available
    # without partner approval - see google_workspace.py-equivalent LinkedIn tools not existing
    # for why) issues short-lived tokens with no refresh grant, so re-connecting is how a user
    # gets a fresh one rather than a background refresh flow.
    access_token: Mapped[str] = mapped_column(String(2000), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    linkedin_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_picture_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
