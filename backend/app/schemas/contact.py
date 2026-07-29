import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ContactUpsert(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    relationship: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=2000)


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    relationship: str | None
    notes: str | None
    last_contact_at: datetime | None
    created_at: datetime
    updated_at: datetime
