from typing import Any

from pydantic import BaseModel


class ToolDefinitionOut(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    permission_level: str
    timeout_seconds: float


class ToolCallRequest(BaseModel):
    arguments: dict[str, Any] = {}


class ToolCallResponse(BaseModel):
    success: bool
    output: Any = None
    error: str | None = None
