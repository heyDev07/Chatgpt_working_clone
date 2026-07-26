import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReminderCreate(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    remind_at: datetime
    conversation_id: uuid.UUID | None = None


class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID | None
    message: str
    remind_at: datetime
    is_delivered: bool
    created_at: datetime
