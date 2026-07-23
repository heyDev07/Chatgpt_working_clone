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
from app.repositories.document_repo import DocumentRepository
from app.repositories.session_repo import SessionRepository
from app.repositories.user_repo import UserRepository
from app.storage.s3_client import delete_object
from app.vectorstore.qdrant_client import delete_document_chunks


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.users = UserRepository(db)
        self.sessions = SessionRepository(db)
        self.documents = DocumentRepository(db)

    async def register(self, email: str, password: str, full_name: str | None) -> User:
        existing = await self.users.get_by_email(email)
        if existing:
            raise ValidationAppError("An account with this email already exists")

        # First account in the system bootstraps as admin - there's no invite/promotion flow
        # yet, so this is the only way an admin account comes to exist.
        is_first_user = await self.users.count() == 0
        user = await self.users.create(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role="admin" if is_first_user else "user",
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

    async def delete_account(self, user: User, password: str) -> None:
        """Permanently deletes the account and everything owned by it. Requires re-entering the
        password (not just a valid session) as a deliberate confirmation step for a destructive,
        irreversible action. Sessions/conversations/messages/memories/folders/tags/tool_call_logs
        all cascade at the DB level via ON DELETE CASCADE on user_id - only document storage
        (MinIO objects, Qdrant vectors) lives outside Postgres and needs explicit cleanup here,
        same as the per-document delete in DocumentService."""
        if not verify_password(password, user.password_hash):
            raise AuthError("Incorrect password")

        documents = await self.documents.list_for_user(user.id)
        for document in documents:
            try:
                await delete_object(document.storage_key)
            except Exception:
                pass
            try:
                await delete_document_chunks(document.id)
            except Exception:
                pass

        await self.users.delete(user)
        await self.db.commit()
