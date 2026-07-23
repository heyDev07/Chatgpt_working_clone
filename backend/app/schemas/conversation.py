import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.message import MessageOut
from app.schemas.tag import TagOut


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    provider: str | None = None
    model: str | None = None


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    is_pinned: bool | None = None
    is_archived: bool | None = None
    provider: str | None = None
    model: str | None = Field(default=None, min_length=1, max_length=100)
    system_prompt: str | None = Field(default=None, max_length=8000)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=32_000)
    top_p: float | None = Field(default=None, ge=0, le=1)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    folder_id: uuid.UUID | None
    tags: list[TagOut] = []
    share_token: str | None
    title: str
    provider: str
    model: str
    is_archived: bool
    is_pinned: bool
    system_prompt: str | None
    temperature: float | None
    max_tokens: int | None
    top_p: float | None
    created_at: datetime
    updated_at: datetime


class ConversationDetailOut(ConversationOut):
    messages: list[MessageOut] = []
