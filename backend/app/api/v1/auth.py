from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_redis
from app.core.exceptions import AuthError
from app.middleware.rate_limit import login_rate_limiter
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # local dev over http; set True behind HTTPS in production
        path="/api/v1/auth",
    )


@router.post("/register", response_model=UserOut, status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> User:
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
        user, request.headers.get("user-agent"), request.client.host if request.client else None
    )

    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token, expires_in=expires_in)


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
