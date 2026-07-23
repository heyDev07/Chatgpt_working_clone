import uuid
from datetime import date as date_type

from pydantic import BaseModel


class DailyUsage(BaseModel):
    date: date_type
    message_count: int
    token_count: int


class UserUsage(BaseModel):
    user_id: uuid.UUID
    email: str
    conversation_count: int
    message_count: int
    token_count: int


class UsageOverview(BaseModel):
    total_users: int
    total_conversations: int
    total_messages: int
    total_tokens: int
    daily: list[DailyUsage]
    top_users: list[UserUsage]
