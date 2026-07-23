import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class UserAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None
    is_active: bool
    is_verified: bool
    role: str
    created_at: datetime


class UserStatusUpdate(BaseModel):
    is_active: bool


class UserRoleUpdate(BaseModel):
    role: Literal["user", "admin"]
