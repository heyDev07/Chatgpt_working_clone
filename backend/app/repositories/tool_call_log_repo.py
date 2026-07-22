import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_call_log import ToolCallLog


class ToolCallLogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: uuid.UUID,
        tool_name: str,
        arguments: dict[str, Any],
        success: bool,
        duration_ms: int,
        output: Any = None,
        error_message: str | None = None,
    ) -> ToolCallLog:
        log = ToolCallLog(
            user_id=user_id,
            tool_name=tool_name,
            arguments=arguments,
            success=success,
            output={"value": output} if output is not None else None,
            error_message=error_message,
            duration_ms=duration_ms,
        )
        self.db.add(log)
        await self.db.flush()
        return log
