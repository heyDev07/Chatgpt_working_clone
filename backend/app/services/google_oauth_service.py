"""Google OAuth (Gmail + Calendar), via plain HTTP calls (httpx, already a dependency) rather
than google-auth-oauthlib/google-api-python-client - this project has consistently avoided heavy
SDKs where a direct REST call does the same job with fewer moving parts (the same reasoning that
kept the SQL tool and image generation tool free of an ORM/SDK for their respective external
calls). OAuth's token exchange and refresh are both just POSTs to a fixed endpoint; Gmail/
Calendar's own APIs are plain REST too.

The authorize/callback split can't both be authenticated the normal way (Authorization: Bearer
header): /authorize is called from the frontend with a real Bearer token and returns a URL to
navigate to, but /callback is Google redirecting the browser back *unauthenticated* - there's no
way to attach a header to a browser-initiated redirect. The user id travels through instead via
a short-lived, HMAC-signed `state` parameter (reusing the app's own JWT secret rather than
inventing a second signing mechanism) - it can't be tampered with to claim someone else's tokens,
and it expires quickly since it only needs to survive one round trip to Google and back.
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
from app.models.google_credential import GoogleCredential

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Widened from read-only to include send/write now that send_gmail/create_calendar_event
# (app/tools/google_workspace.py) exist - both of those are gated behind the human-in-the-loop
# confirmation flow (tool_confirmation.py), which is what makes granting write scopes here an
# acceptable tradeoff rather than handing the model unsupervised send/write access. Anyone who
# connected under the old read-only scope set needs to reconnect (Disconnect + Connect again in
# Settings) to actually get gmail.send/calendar.events on their stored credential - Google won't
# retroactively widen an already-issued token's scope.
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "openid",
    "email",
]

_STATE_TTL_SECONDS = 600


def _sign_state(user_id: uuid.UUID) -> str:
    settings = get_settings()
    return jwt.encode(
        {"user_id": str(user_id), "exp": int(time.time()) + _STATE_TTL_SECONDS},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def _verify_state(state: str) -> uuid.UUID:
    settings = get_settings()
    try:
        payload = jwt.decode(state, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise ValidationAppError(f"Invalid or expired OAuth state: {exc}") from exc
    return uuid.UUID(payload["user_id"])


class GoogleOAuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def build_authorize_url(self, user_id: uuid.UUID) -> str:
        settings = get_settings()
        if not settings.google_client_id:
            raise ValidationAppError("Google OAuth is not configured on this server")
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": " ".join(GOOGLE_SCOPES),
            "access_type": "offline",  # required to get a refresh_token back at all
            "prompt": "consent",  # forces a fresh refresh_token even on a repeat connect
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
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_oauth_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            tokens = token_response.json()

            userinfo_response = await request_with_retry(
                client, "GET", USERINFO_URL, headers={"Authorization": f"Bearer {tokens['access_token']}"}
            )
            userinfo_response.raise_for_status()
            google_email = userinfo_response.json().get("email")

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens.get("expires_in", 3600))

        result = await self.db.execute(select(GoogleCredential).where(GoogleCredential.user_id == user_id))
        existing = result.scalar_one_or_none()
        if existing:
            existing.access_token = tokens["access_token"]
            # Google only returns refresh_token on the *first* consent (or when prompt=consent
            # forces re-consent, which build_authorize_url always sets) - falling back to the
            # existing one covers the rare case it's still missing so a reconnect never
            # silently downgrades to an access-only (soon to expire, unrenewable) credential.
            existing.refresh_token = tokens.get("refresh_token") or existing.refresh_token
            existing.expires_at = expires_at
            existing.scopes = tokens.get("scope", "")
            existing.google_email = google_email
        else:
            self.db.add(
                GoogleCredential(
                    user_id=user_id,
                    access_token=tokens["access_token"],
                    refresh_token=tokens.get("refresh_token"),
                    expires_at=expires_at,
                    scopes=tokens.get("scope", ""),
                    google_email=google_email,
                )
            )
        await self.db.commit()
        return user_id

    async def get_valid_access_token(self, user_id: uuid.UUID) -> str:
        """Returns a live access token, refreshing it first if it's expired - Gmail/Calendar
        access tokens are short-lived (~1hr) by design, so any real usage needs this, not just
        the one-time token from the initial OAuth completion."""
        result = await self.db.execute(select(GoogleCredential).where(GoogleCredential.user_id == user_id))
        credential = result.scalar_one_or_none()
        if not credential:
            raise ValidationAppError("Google account not connected")

        if credential.expires_at > datetime.now(timezone.utc) + timedelta(seconds=30):
            return credential.access_token

        if not credential.refresh_token:
            raise ValidationAppError("Google access token expired and no refresh token is available - reconnect")

        settings = get_settings()
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await request_with_retry(
                client,
                "POST",
                TOKEN_URL,
                data={
                    "refresh_token": credential.refresh_token,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            tokens = response.json()

        credential.access_token = tokens["access_token"]
        credential.expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens.get("expires_in", 3600))
        await self.db.commit()
        return credential.access_token

    async def get_status(self, user_id: uuid.UUID) -> GoogleCredential | None:
        result = await self.db.execute(select(GoogleCredential).where(GoogleCredential.user_id == user_id))
        return result.scalar_one_or_none()

    async def disconnect(self, user_id: uuid.UUID) -> None:
        credential = await self.get_status(user_id)
        if credential:
            await self.db.delete(credential)
            await self.db.commit()
