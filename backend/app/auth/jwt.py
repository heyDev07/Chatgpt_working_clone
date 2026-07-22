import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.config.settings import get_settings
from app.core.exceptions import AuthError

settings = get_settings()


def create_access_token(user_id: str) -> tuple[str, int]:
    expire_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expires_at = datetime.now(timezone.utc) + expire_delta
    payload = {"sub": user_id, "exp": expires_at, "type": "access"}
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, int(expire_delta.total_seconds())


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Access token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("Invalid access token") from exc

    if payload.get("type") != "access":
        raise AuthError("Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthError("Invalid token payload")
    return user_id


def generate_refresh_token() -> str:
    """An opaque, high-entropy token. Only its hash is stored server-side."""
    return secrets.token_urlsafe(48)


def refresh_token_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
