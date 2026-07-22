from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    refresh_token_expiry,
)
from app.auth.password import hash_password, verify_password
from app.core.exceptions import AuthError, ValidationAppError
from app.models.user import User
from app.repositories.session_repo import SessionRepository
from app.repositories.user_repo import UserRepository


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.users = UserRepository(db)
        self.sessions = SessionRepository(db)

    async def register(self, email: str, password: str, full_name: str | None) -> User:
        existing = await self.users.get_by_email(email)
        if existing:
            raise ValidationAppError("An account with this email already exists")

        user = await self.users.create(
            email=email, password_hash=hash_password(password), full_name=full_name
        )
        await self.db.commit()
        return user

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.users.get_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise AuthError("Invalid email or password")
        if not user.is_active:
            raise AuthError("Account is disabled")
        return user

    async def issue_tokens(
        self, user: User, user_agent: str | None, ip_address: str | None
    ) -> tuple[str, int, str]:
        access_token, expires_in = create_access_token(str(user.id))

        refresh_token = generate_refresh_token()
        await self.sessions.create(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(refresh_token),
            expires_at=refresh_token_expiry(),
            user_agent=user_agent,
            ip_address=ip_address,
        )
        await self.db.commit()
        return access_token, expires_in, refresh_token

    async def rotate_refresh_token(
        self, refresh_token: str, user_agent: str | None, ip_address: str | None
    ) -> tuple[str, int, str]:
        session = await self.sessions.get_active_by_token_hash(hash_refresh_token(refresh_token))
        if not session:
            raise AuthError("Invalid or expired refresh token")

        user = await self.users.get_by_id(session.user_id)
        if not user or not user.is_active:
            raise AuthError("Invalid or expired refresh token")

        await self.sessions.revoke(session)
        return await self.issue_tokens(user, user_agent, ip_address)

    async def logout(self, refresh_token: str) -> None:
        session = await self.sessions.get_active_by_token_hash(hash_refresh_token(refresh_token))
        if session:
            await self.sessions.revoke(session)
            await self.db.commit()
