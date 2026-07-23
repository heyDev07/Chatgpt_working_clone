from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User


class AnalyticsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def total_users(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(User))
        return result.scalar_one()

    async def total_conversations(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(Conversation))
        return result.scalar_one()

    async def total_messages(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(Message))
        return result.scalar_one()

    async def total_tokens(self) -> int:
        result = await self.db.execute(select(func.coalesce(func.sum(Message.token_count), 0)))
        return result.scalar_one()

    async def daily_usage(self, days: int) -> list[tuple[datetime, int, int]]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        day = func.date_trunc("day", Message.created_at).label("day")
        query = (
            select(day, func.count(Message.id), func.coalesce(func.sum(Message.token_count), 0))
            .where(Message.created_at >= since)
            .group_by(day)
            .order_by(day)
        )
        result = await self.db.execute(query)
        return list(result.all())

    async def top_users(self, limit: int) -> list[tuple[User, int, int, int]]:
        query = (
            select(
                User,
                func.count(func.distinct(Conversation.id)),
                func.count(Message.id),
                func.coalesce(func.sum(Message.token_count), 0),
            )
            .join(Conversation, Conversation.user_id == User.id, isouter=True)
            .join(Message, Message.conversation_id == Conversation.id, isouter=True)
            .group_by(User.id)
            .order_by(func.count(Message.id).desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.all())
