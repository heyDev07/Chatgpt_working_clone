import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.attachment import AttachmentOut


class MessageCreate(BaseModel):
    # No min_length: an image-only message ("just send the picture, no caption") is valid, as
    # long as attachment_ids covers it - enforced below rather than by the field itself, since
    # content alone can't tell "empty and invalid" from "empty but there's an image".
    content: str = Field(default="", max_length=32_000)
    provider: str | None = None
    model: str | None = None
    # IDs from a prior POST /attachments/upload - uploaded separately (so the composer can show
    # a preview immediately on file-select) and linked to this message once it's created.
    attachment_ids: list[uuid.UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_content_or_attachment(self) -> "MessageCreate":
        if not self.content.strip() and not self.attachment_ids:
            raise ValueError("content must not be empty unless attachment_ids is provided")
        return self


class MessageFeedbackUpdate(BaseModel):
    feedback: Literal["up", "down", None] = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    token_count: int | None
    model: str | None
    finish_reason: str | None
    feedback: str | None
    agent: str | None
    attachments: list[AttachmentOut] = Field(default_factory=list)
    created_at: datetime
