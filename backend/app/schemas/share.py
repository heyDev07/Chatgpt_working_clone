from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SharedMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str
    content: str
    created_at: datetime


class SharedConversationOut(BaseModel):
    """Deliberately minimal - only what a public, no-auth viewer should see. No ids, no
    provider/model, no user info, nothing beyond the transcript itself."""

    model_config = ConfigDict(from_attributes=True)

    title: str
    messages: list[SharedMessageOut]
    created_at: datetime
