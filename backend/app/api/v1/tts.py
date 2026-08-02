from fastapi import APIRouter, Depends, Response
from redis.asyncio import Redis

from app.api.deps import get_current_user, get_redis
from app.middleware.rate_limit import tts_rate_limiter
from app.models.user import User
from app.schemas.tts import TTSRequest
from app.services.tts_service import DEFAULT_VOICE, synthesize_speech

router = APIRouter(prefix="/tts", tags=["tts"])


@router.post("")
async def text_to_speech(
    payload: TTSRequest,
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> Response:
    # Not conversation-scoped (unlike every /conversations/{id}/... route) - this is a stateless
    # "synthesize this text" call, same reasoning /documents/upload isn't scoped to a
    # conversation either. Powers voice mode: one call per sentence as the reply streams in.
    await tts_rate_limiter.check(redis, identifier=str(current_user.id))
    audio = await synthesize_speech(payload.text, voice=payload.voice or DEFAULT_VOICE)
    return Response(content=audio, media_type="audio/wav")
