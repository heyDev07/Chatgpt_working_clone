import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_provider_manager, get_redis
from app.db.database import async_session_factory
from app.middleware.rate_limit import message_rate_limiter
from app.models.user import User
from app.providers.provider_manager import ProviderManager
from app.schemas.message import MessageCreate
from app.services.chat_service import ChatService

router = APIRouter(prefix="/conversations", tags=["messages"])


def _format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    provider_manager: ProviderManager = Depends(get_provider_manager),
    redis: Redis = Depends(get_redis),
) -> StreamingResponse:
    await message_rate_limiter.check(redis, identifier=str(current_user.id))

    # Must resolve + authorize the conversation using the request-scoped session, before the
    # StreamingResponse is constructed: once streaming starts, a 200 status is already
    # committed and a 404 can no longer be sent.
    await ChatService(db, provider_manager).get_authorized_conversation(conversation_id, current_user.id)

    async def event_stream() -> AsyncIterator[str]:
        # FastAPI tears down Depends(get_db) when the route function *returns*, which for a
        # StreamingResponse happens before this generator is ever iterated - so it can't reuse
        # `db` above. Open a session scoped to the generator's own lifetime instead.
        async with async_session_factory() as stream_db:
            stream_service = ChatService(stream_db, provider_manager)
            async for event in stream_service.stream_message(
                conversation_id, current_user.id, payload.content
            ):
                yield _format_sse(event["event"], event["data"])

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{conversation_id}/messages/{message_id}/edit")
async def edit_message(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    provider_manager: ProviderManager = Depends(get_provider_manager),
    redis: Redis = Depends(get_redis),
) -> StreamingResponse:
    await message_rate_limiter.check(redis, identifier=str(current_user.id))

    await ChatService(db, provider_manager).get_authorized_conversation(conversation_id, current_user.id)

    async def event_stream() -> AsyncIterator[str]:
        async with async_session_factory() as stream_db:
            stream_service = ChatService(stream_db, provider_manager)
            async for event in stream_service.edit_message(
                conversation_id, current_user.id, message_id, payload.content
            ):
                yield _format_sse(event["event"], event["data"])

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{conversation_id}/regenerate")
async def regenerate_message(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    provider_manager: ProviderManager = Depends(get_provider_manager),
    redis: Redis = Depends(get_redis),
) -> StreamingResponse:
    await message_rate_limiter.check(redis, identifier=str(current_user.id))

    await ChatService(db, provider_manager).get_authorized_conversation(conversation_id, current_user.id)

    async def event_stream() -> AsyncIterator[str]:
        async with async_session_factory() as stream_db:
            stream_service = ChatService(stream_db, provider_manager)
            async for event in stream_service.regenerate(conversation_id, current_user.id):
                yield _format_sse(event["event"], event["data"])

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
