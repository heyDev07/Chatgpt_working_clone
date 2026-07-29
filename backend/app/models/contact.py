import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Contact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "contacts"
    # Same-name contacts are merged by upsert_contact rather than creating duplicates (the exact
    # problem found and fixed in memory extraction) - the DB constraint is the real backstop,
    # the service-layer lookup-by-name is just what makes that the normal path rather than a
    # conflict error.
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_contacts_user_id_name"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    relationship: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Freeform, append-only log of notes about this person - not a single overwritten summary,
    # so "talked about the promo on the 3rd" doesn't get silently lost when a later note is
    # added. Rendered as-is (each upsert appends a new line), not restructured into a table.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
