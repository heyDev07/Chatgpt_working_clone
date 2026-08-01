""""Sign in with Google" - creates or logs into an app account via Google's identity, additive
to (not a replacement for) the existing email/password flow in auth_service.py. Deliberately kept
as its own module rather than folded into google_oauth_service.py: that service attaches
Gmail/Calendar credentials to an *already-authenticated* user (state carries a user_id), while
this flow runs with no session at all - state here is just a CSRF nonce, and the callback's job is
to resolve or create a User row and hand back this app's own tokens, not store a GoogleCredential.
"""

import secrets
import time
import uuid

import httpx
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.password import hash_password
from app.config.settings import get_settings
from app.core.exceptions import ValidationAppError
from app.repositories.user_repo import UserRepository
from app.services.auth_service import AuthService

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

GOOGLE_LOGIN_SCOPES = ["openid", "email", "profile"]

_STATE_TTL_SECONDS = 600


def _sign_login_state() -> str:
    settings = get_settings()
    # No user_id to embed (nobody's logged in yet) - this is pure CSRF protection, proving the
    # callback is completing a flow this server actually started.
    return jwt.encode(
        {"purpose": "google_login", "nonce": secrets.token_urlsafe(16), "exp": int(time.time()) + _STATE_TTL_SECONDS},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def _verify_login_state(state: str) -> None:
    settings = get_settings()
    try:
        payload = jwt.decode(state, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise ValidationAppError(f"Invalid or expired OAuth state: {exc}") from exc
    if payload.get("purpose") != "google_login":
        raise ValidationAppError("Invalid OAuth state")


def build_login_authorize_url() -> str:
    settings = get_settings()
    if not settings.google_login_client_id:
        raise ValidationAppError("Google sign-in is not configured on this server")
    params = {
        "client_id": settings.google_login_client_id,
        "redirect_uri": settings.google_login_redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_LOGIN_SCOPES),
        "state": _sign_login_state(),
    }
    return f"{AUTHORIZE_URL}?{httpx.QueryParams(params)}"


async def handle_login_callback(
    db: AsyncSession, code: str, state: str, user_agent: str | None, ip_address: str | None
) -> tuple[str, int, str]:
    """Exchanges the code, resolves the Google profile to an existing or brand-new User (matched
    by email - an existing password-based account with the same address just gains a second way
    in), and issues this app's own access/refresh tokens exactly as a normal password login
    would. Returns the same (access_token, expires_in, refresh_token) tuple as
    AuthService.issue_tokens so the API route can set the cookie identically."""
    _verify_login_state(state)
    settings = get_settings()

    async with httpx.AsyncClient(timeout=15.0) as client:
        token_response = await client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_login_client_id,
                "client_secret": settings.google_login_client_secret,
                "redirect_uri": settings.google_login_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_response.raise_for_status()
        tokens = token_response.json()

        userinfo_response = await client.get(
            USERINFO_URL, headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )
        userinfo_response.raise_for_status()
        profile = userinfo_response.json()

    email = profile.get("email")
    if not email:
        raise ValidationAppError("Google did not return an email address for this account")

    users = UserRepository(db)
    user = await users.get_by_email(email)
    if not user:
        is_first_user = await users.count() == 0
        # Random, never-communicated password - this account can only ever be reached via
        # Google sign-in unless the user separately sets a password (not yet built), the same
        # "second way in" principle applied to a fresh account rather than an existing one.
        user = await users.create(
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            full_name=profile.get("name"),
            role="admin" if is_first_user else "user",
        )
        await db.commit()

    if not user.is_active:
        raise ValidationAppError("Account is disabled")

    return await AuthService(db).issue_tokens(user, user_agent, ip_address)
