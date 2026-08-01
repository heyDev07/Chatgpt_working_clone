"""LinkedIn connect (profile identity only), via plain httpx - same reasoning as
google_oauth_service.py for avoiding a heavy SDK.

Scoped deliberately to LinkedIn's self-serve "Sign In with LinkedIn using OpenID Connect"
product (openid/profile/email scopes) - reading connections, posts, or anything beyond basic
identity requires LinkedIn's Marketing/Partner API products, which need a business application
and manual LinkedIn approval that isn't available to an indie project. This connects an account
and stores name/email/photo, same shape as GoogleCredential, not a tools-with-real-capability
integration the way google_workspace.py's Gmail/Calendar tools are - there is currently no
"list my LinkedIn connections" tool because LinkedIn's API genuinely doesn't offer that access
tier outside partnership.

Same authorize/callback split and signed-state reasoning as google_oauth_service.py's docstring.
"""

import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.core.exceptions import ValidationAppError
from app.core.http_retry import request_with_retry
from app.models.linkedin_credential import LinkedInCredential

AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

LINKEDIN_SCOPES = ["openid", "profile", "email"]

_STATE_TTL_SECONDS = 600


def _sign_state(user_id: uuid.UUID) -> str:
    settings = get_settings()
    return jwt.encode(
        {"purpose": "linkedin_connect", "user_id": str(user_id), "exp": int(time.time()) + _STATE_TTL_SECONDS},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def _verify_state(state: str) -> uuid.UUID:
    settings = get_settings()
    try:
        payload = jwt.decode(state, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise ValidationAppError(f"Invalid or expired OAuth state: {exc}") from exc
    if payload.get("purpose") != "linkedin_connect":
        raise ValidationAppError("Invalid OAuth state")
    return uuid.UUID(payload["user_id"])


class LinkedInOAuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def build_authorize_url(self, user_id: uuid.UUID) -> str:
        settings = get_settings()
        if not settings.linkedin_client_id:
            raise ValidationAppError("LinkedIn connect is not configured on this server")
        params = {
            "client_id": settings.linkedin_client_id,
            "redirect_uri": settings.linkedin_oauth_redirect_uri,
            "response_type": "code",
            "scope": " ".join(LINKEDIN_SCOPES),
            "state": _sign_state(user_id),
        }
        return f"{AUTHORIZE_URL}?{httpx.QueryParams(params)}"

    async def handle_callback(self, code: str, state: str) -> uuid.UUID:
        user_id = _verify_state(state)
        settings = get_settings()

        async with httpx.AsyncClient(timeout=15.0) as client:
            token_response = await request_with_retry(
                client,
                "POST",
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": settings.linkedin_client_id,
                    "client_secret": settings.linkedin_client_secret,
                    "redirect_uri": settings.linkedin_oauth_redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_response.raise_for_status()
            tokens = token_response.json()

            userinfo_response = await request_with_retry(
                client, "GET", USERINFO_URL, headers={"Authorization": f"Bearer {tokens['access_token']}"}
            )
            userinfo_response.raise_for_status()
            profile = userinfo_response.json()

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens.get("expires_in", 3600))

        result = await self.db.execute(select(LinkedInCredential).where(LinkedInCredential.user_id == user_id))
        existing = result.scalar_one_or_none()
        if existing:
            existing.access_token = tokens["access_token"]
            existing.expires_at = expires_at
            existing.linkedin_name = profile.get("name")
            existing.linkedin_email = profile.get("email")
            existing.profile_picture_url = profile.get("picture")
        else:
            self.db.add(
                LinkedInCredential(
                    user_id=user_id,
                    access_token=tokens["access_token"],
                    expires_at=expires_at,
                    linkedin_name=profile.get("name"),
                    linkedin_email=profile.get("email"),
                    profile_picture_url=profile.get("picture"),
                )
            )
        await self.db.commit()
        return user_id

    async def get_status(self, user_id: uuid.UUID) -> LinkedInCredential | None:
        result = await self.db.execute(select(LinkedInCredential).where(LinkedInCredential.user_id == user_id))
        return result.scalar_one_or_none()

    async def disconnect(self, user_id: uuid.UUID) -> None:
        credential = await self.get_status(user_id)
        if credential:
            await self.db.delete(credential)
            await self.db.commit()
