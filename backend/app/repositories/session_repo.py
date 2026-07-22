import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session


class SessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: uuid.UUID,
        refresh_token_hash: str,
        expires_at: datetime,
        user_agent: str | None,
        ip_address: str | None,
    ) -> Session:
        session = Session(
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def get_active_by_token_hash(self, refresh_token_hash: str) -> Session | None:
        result = await self.db.execute(
            select(Session).where(
                Session.refresh_token_hash == refresh_token_hash,
                Session.revoked_at.is_(None),
            )
        )
        session = result.scalar_one_or_none()
        if session and session.expires_at < datetime.now(timezone.utc):
            return None
        return session

    async def revoke(self, session: Session) -> None:
        session.revoked_at = datetime.now(timezone.utc)
        await self.db.flush()
