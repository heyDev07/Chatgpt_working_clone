from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_redis
from app.config.settings import get_settings
from app.core.exceptions import AuthError
from app.middleware.rate_limit import login_rate_limiter, register_rate_limiter
from app.models.user import User
from app.schemas.auth import DeleteAccountRequest, LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services import google_login_service
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=get_settings().is_production,
        path="/api/v1/auth",
    )


@router.post("/register", response_model=UserOut, status_code=201)
async def register(
    payload: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> User:
    # No user identity exists yet to key a limiter on - IP is the only identifier available,
    # same reasoning as any other pre-auth endpoint.
    identifier = request.client.host if request.client else "unknown"
    await register_rate_limiter.check(redis, identifier=identifier)

    service = AuthService(db)
    return await service.register(payload.email, payload.password, payload.full_name)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TokenResponse:
    await login_rate_limiter.check(redis, identifier=payload.email)

    service = AuthService(db)
    user = await service.authenticate(payload.email, payload.password)
    access_token, expires_in, refresh_token = await service.issue_tokens(
        user,
        request.headers.get("user-agent"),
        request.client.host if request.client else None,
        login_method="password",
    )

    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token, expires_in=expires_in)


@router.get("/google/authorize")
async def google_authorize() -> RedirectResponse:
    # A true redirect, not a JSON URL-to-navigate-to like oauth.py's Gmail-connect authorize -
    # this route needs no Bearer token (nobody's logged in yet), so the frontend can link/navigate
    # straight to it instead of needing an authenticated fetch first.
    return RedirectResponse(url=google_login_service.build_login_authorize_url())


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    # Unauthenticated by design, same reasoning as oauth.py's callback - this is Google
    # redirecting the browser back, not an API call this app's own frontend makes.
    _access_token, _expires_in, refresh_token = await google_login_service.handle_login_callback(
        db, code, state, request.headers.get("user-agent"), request.client.host if request.client else None
    )
    # AuthProvider (frontend) picks the session up itself on mount via POST /auth/refresh, which
    # reads the cookie set below - no need to pass the access_token through the URL at all. Set on
    # the actually-returned RedirectResponse directly - the injected Response param FastAPI
    # normally merges cookies from only applies to non-Response return values (see login() above),
    # not when the handler returns its own Response subclass like this one does.
    redirect = RedirectResponse(url="http://localhost:3000/chat")
    _set_refresh_cookie(redirect, refresh_token)
    return redirect


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise AuthError("Missing refresh token")

    service = AuthService(db)
    access_token, expires_in, new_refresh_token = await service.rotate_refresh_token(
        refresh_token, request.headers.get("user-agent"), request.client.host if request.client else None
    )

    _set_refresh_cookie(response, new_refresh_token)
    return TokenResponse(access_token=access_token, expires_in=expires_in)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> None:
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token:
        await AuthService(db).logout(refresh_token)
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/v1/auth")


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.delete("/me", status_code=204)
async def delete_account(
    payload: DeleteAccountRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await AuthService(db).delete_account(current_user, payload.password)
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/v1/auth")
