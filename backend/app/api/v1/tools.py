from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_redis
from app.middleware.rate_limit import tool_call_rate_limiter
from app.models.user import User
from app.schemas.tool import ToolCallRequest, ToolCallResponse, ToolDefinitionOut
from app.tools.registry import ToolRegistry, get_tool_registry
from app.tools.router import ToolRouter

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("", response_model=list[ToolDefinitionOut])
async def list_tools(
    current_user: User = Depends(get_current_user),
    registry: ToolRegistry = Depends(get_tool_registry),
):
    return [
        ToolDefinitionOut(
            name=d.name,
            description=d.description,
            input_schema=d.input_schema,
            permission_level=d.permission_level,
            timeout_seconds=d.timeout_seconds,
        )
        for d in registry.list_definitions()
    ]


@router.post("/{tool_name}/call", response_model=ToolCallResponse)
async def call_tool(
    tool_name: str,
    body: ToolCallRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    registry: ToolRegistry = Depends(get_tool_registry),
):
    # Every tool call is a real resource cost (external API request, DB query, and - via
    # chat_service's own path - a spawned browser process), unlike a plain read endpoint.
    await tool_call_rate_limiter.check(redis, identifier=str(current_user.id))
    result = await ToolRouter(db, registry).call(current_user.id, tool_name, body.arguments)
    return ToolCallResponse(success=result.success, output=result.output, error=result.error)
