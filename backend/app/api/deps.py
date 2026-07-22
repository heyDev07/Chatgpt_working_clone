import uuid
from collections.abc import AsyncIterator

from fastapi import Depends, Header
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_access_token
from app.core.exceptions import AuthError
from app.db.database import get_db_session
from app.db.redis_client import get_redis as _get_redis
from app.models.user import User
from app.repositories.user_repo import UserRepository


async def get_db(session: AsyncSession = Depends(get_db_session)) -> AsyncIterator[AsyncSession]:
    yield session


def get_redis() -> Redis:
    return _get_redis()


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1]
    user_id = decode_access_token(token)

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError as exc:
        raise AuthError("Invalid token subject") from exc

    user = await UserRepository(db).get_by_id(user_uuid)
    if not user or not user.is_active:
        raise AuthError("User not found or inactive")
    return user
