import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class GoogleCredential(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "google_credentials"

    # One Google connection per app user - a second OAuth completion for the same user
    # overwrites rather than creating a second row (see GoogleOAuthService.store_tokens).
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # Plaintext for now, matching how every other credential in this app (TAVILY_API_KEY, the
    # LLM provider keys) is stored - unlike those, this is the *user's own* real account access,
    # not a service credential this app owns, so encrypting these at rest is a real gap worth
    # closing before this goes anywhere near production. Flagged here deliberately rather than
    # silently treating it as equivalent to the app's own service keys.
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scopes: Mapped[str] = mapped_column(String(500), nullable=False)
    google_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
