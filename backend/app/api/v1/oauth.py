import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import ValidationAppError
from app.models.user import User
from app.services.google_oauth_service import GoogleOAuthService

router = APIRouter(prefix="/oauth/google", tags=["oauth"])


def _get_service(db: AsyncSession = Depends(get_db)) -> GoogleOAuthService:
    return GoogleOAuthService(db)


@router.get("/authorize")
async def authorize(
    current_user: User = Depends(get_current_user),
    service: GoogleOAuthService = Depends(_get_service),
) -> dict:
    # Returns the URL rather than redirecting directly - this endpoint is called as an
    # authenticated fetch (needs the Bearer token to know which user is connecting), and a
    # window.location navigation can't carry that header, so the frontend does the actual
    # navigation itself once it has the URL.
    return {"authorize_url": service.build_authorize_url(current_user.id)}


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(...),
    service: GoogleOAuthService = Depends(_get_service),
) -> RedirectResponse:
    # Unauthenticated by design - this is Google redirecting the user's browser back, not an
    # API call from the frontend, so there's no Bearer token to check here. The signed `state`
    # (see google_oauth_service._verify_state) is the actual security boundary: it's what
    # proves which user this callback belongs to, not this route's own auth.
    await service.handle_callback(code, state)
    # /settings isn't a routed page in this app - Settings is a client-side modal opened by
    # state, not a URL. Redirects to /chat instead, with a query param the chat layout checks
    # for on mount to auto-open that modal (see app/(chat)/layout.tsx).
    return RedirectResponse(url="http://localhost:3000/chat?google_connected=true")


@router.get("/status")
async def status(
    current_user: User = Depends(get_current_user),
    service: GoogleOAuthService = Depends(_get_service),
) -> dict:
    credential = await service.get_status(current_user.id)
    if not credential:
        return {"connected": False}
    return {"connected": True, "google_email": credential.google_email, "scopes": credential.scopes}


@router.post("/disconnect", status_code=204)
async def disconnect(
    current_user: User = Depends(get_current_user),
    service: GoogleOAuthService = Depends(_get_service),
) -> None:
    await service.disconnect(current_user.id)


@router.get("/test")
async def test_connection(
    current_user: User = Depends(get_current_user),
    service: GoogleOAuthService = Depends(_get_service),
) -> dict:
    """Proves the OAuth credentials actually work, not just that a token got stored - makes a
    real Gmail API call (profile: total message count + the connected address) using the stored
    access token, refreshing it first if needed. This is the direct answer to "does this Gmail
    API key thing actually work" rather than just checking a row exists in the database."""
    access_token = await service.get_valid_access_token(current_user.id)
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/profile",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code != 200:
        raise ValidationAppError(f"Gmail API call failed: {response.status_code} {response.text}")
    profile = response.json()
    return {
        "email_address": profile.get("emailAddress"),
        "total_messages": profile.get("messagesTotal"),
        "total_threads": profile.get("threadsTotal"),
    }
