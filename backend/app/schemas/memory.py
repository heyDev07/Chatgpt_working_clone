import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MemoryUpdate(BaseModel):
    memory_text: str | None = Field(default=None, min_length=1, max_length=2000)
    category: str | None = Field(default=None, max_length=50)
    importance: float | None = Field(default=None, ge=0, le=1)


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str
    memory_text: str
    importance: float
    created_at: datetime
    updated_at: datetime
