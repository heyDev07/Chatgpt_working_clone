import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=32_000)
    provider: str | None = None
    model: str | None = None


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
    created_at: datetime
