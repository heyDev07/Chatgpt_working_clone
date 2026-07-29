from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.linkedin_oauth_service import LinkedInOAuthService

router = APIRouter(prefix="/oauth/linkedin", tags=["oauth"])


def _get_service(db: AsyncSession = Depends(get_db)) -> LinkedInOAuthService:
    return LinkedInOAuthService(db)


@router.get("/authorize")
async def authorize(
    current_user: User = Depends(get_current_user),
    service: LinkedInOAuthService = Depends(_get_service),
) -> dict:
    # Same reasoning as oauth.py's Gmail authorize - returns the URL for the frontend to
    # navigate to itself, rather than redirecting directly, since this needs the Bearer token.
    return {"authorize_url": service.build_authorize_url(current_user.id)}


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(...),
    service: LinkedInOAuthService = Depends(_get_service),
) -> RedirectResponse:
    # Unauthenticated by design, same reasoning as oauth.py's Gmail callback.
    await service.handle_callback(code, state)
    return RedirectResponse(url="http://localhost:3000/chat?linkedin_connected=true")


@router.get("/status")
async def status(
    current_user: User = Depends(get_current_user),
    service: LinkedInOAuthService = Depends(_get_service),
) -> dict:
    credential = await service.get_status(current_user.id)
    if not credential:
        return {"connected": False}
    return {
        "connected": True,
        "linkedin_name": credential.linkedin_name,
        "linkedin_email": credential.linkedin_email,
        "profile_picture_url": credential.profile_picture_url,
    }


@router.post("/disconnect", status_code=204)
async def disconnect(
    current_user: User = Depends(get_current_user),
    service: LinkedInOAuthService = Depends(_get_service),
) -> None:
    await service.disconnect(current_user.id)
