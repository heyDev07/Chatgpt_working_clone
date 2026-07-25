import asyncio
import time
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.metrics import tool_call_duration_seconds, tool_calls_total
from app.repositories.tool_call_log_repo import ToolCallLogRepository
from app.tools.base import ToolResult
from app.tools.registry import ToolRegistry


class ToolRouter:
    """Single entry point for executing a tool call: looks it up in the registry, enforces a
    per-tool timeout, and always records an audit log entry - on success or failure - before
    returning. Callers (chat_service's future tool-calling loop, or a direct API route) never
    call a tool's .run() themselves."""

    def __init__(self, db: AsyncSession, registry: ToolRegistry):
        self.db = db
        self.registry = registry
        self.logs = ToolCallLogRepository(db)

    async def call(self, user_id: uuid.UUID, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        tool = self.registry.get(tool_name)
        if not tool:
            raise NotFoundError(f"Unknown tool '{tool_name}'")

        started = time.monotonic()
        try:
            output = await asyncio.wait_for(tool.run(**arguments), timeout=tool.definition.timeout_seconds)
            duration = time.monotonic() - started
            duration_ms = int(duration * 1000)
            await self.logs.create(user_id, tool_name, arguments, success=True, duration_ms=duration_ms, output=output)
            await self.db.commit()
            tool_calls_total.labels(tool_name=tool_name, success="true").inc()
            tool_call_duration_seconds.labels(tool_name=tool_name).observe(duration)
            return ToolResult(success=True, output=output)
        except asyncio.TimeoutError:
            duration = time.monotonic() - started
            duration_ms = int(duration * 1000)
            error = f"Tool '{tool_name}' timed out after {tool.definition.timeout_seconds}s"
            await self.logs.create(user_id, tool_name, arguments, success=False, duration_ms=duration_ms, error_message=error)
            await self.db.commit()
            tool_calls_total.labels(tool_name=tool_name, success="false").inc()
            tool_call_duration_seconds.labels(tool_name=tool_name).observe(duration)
            return ToolResult(success=False, error=error)
        except Exception as exc:
            duration = time.monotonic() - started
            duration_ms = int(duration * 1000)
            error = str(exc)
            await self.logs.create(user_id, tool_name, arguments, success=False, duration_ms=duration_ms, error_message=error)
            await self.db.commit()
            tool_calls_total.labels(tool_name=tool_name, success="false").inc()
            tool_call_duration_seconds.labels(tool_name=tool_name).observe(duration)
            return ToolResult(success=False, error=error)
