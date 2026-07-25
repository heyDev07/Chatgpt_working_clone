import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_redis
from app.middleware.rate_limit import upload_rate_limiter
from app.models.user import User
from app.schemas.attachment import AttachmentOut
from app.services.attachment_service import AttachmentService

router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.post("/upload", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    await upload_rate_limiter.check(redis, identifier=str(current_user.id))
    return await AttachmentService(db).upload(current_user.id, file)


@router.get("/{attachment_id}/content")
async def get_attachment_content(
    attachment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # A plain <img src> can't carry an Authorization header, so the frontend fetches this with
    # its auth header attached and renders the result as a blob URL rather than pointing <img>
    # straight at this endpoint.
    data, content_type = await AttachmentService(db).get_content(attachment_id, current_user.id)
    return Response(content=data, media_type=content_type)
