from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.analytics_repo import AnalyticsRepository
from app.schemas.analytics import DailyUsage, UsageOverview, UserUsage


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.analytics = AnalyticsRepository(db)

    async def get_overview(self, *, days: int = 14, top_n: int = 10) -> UsageOverview:
        daily_rows = await self.analytics.daily_usage(days)
        top_rows = await self.analytics.top_users(top_n)

        return UsageOverview(
            total_users=await self.analytics.total_users(),
            total_conversations=await self.analytics.total_conversations(),
            total_messages=await self.analytics.total_messages(),
            total_tokens=await self.analytics.total_tokens(),
            daily=[
                DailyUsage(date=day.date(), message_count=count, token_count=tokens)
                for day, count, tokens in daily_rows
            ],
            top_users=[
                UserUsage(
                    user_id=user.id,
                    email=user.email,
                    conversation_count=conv_count,
                    message_count=msg_count,
                    token_count=tokens,
                )
                for user, conv_count, msg_count, tokens in top_rows
                if msg_count > 0
            ],
        )
