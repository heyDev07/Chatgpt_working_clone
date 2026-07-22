import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_summary import ConversationSummary


class ConversationSummaryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, conversation_id: uuid.UUID) -> ConversationSummary | None:
        result = await self.db.execute(
            select(ConversationSummary).where(ConversationSummary.conversation_id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self, conversation_id: uuid.UUID, summary: str, summarized_through_message_id: uuid.UUID
    ) -> ConversationSummary:
        existing = await self.get(conversation_id)
        if existing:
            existing.summary = summary
            existing.summarized_through_message_id = summarized_through_message_id
            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        row = ConversationSummary(
            conversation_id=conversation_id,
            summary=summary,
            summarized_through_message_id=summarized_through_message_id,
        )
        self.db.add(row)
        await self.db.flush()
        return row
