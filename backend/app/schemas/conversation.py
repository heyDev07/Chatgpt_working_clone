import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.message import MessageOut


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    provider: str | None = None
    model: str | None = None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    provider: str
    model: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class ConversationDetailOut(ConversationOut):
    messages: list[MessageOut] = []
