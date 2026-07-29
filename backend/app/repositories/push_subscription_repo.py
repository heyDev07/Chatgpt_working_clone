import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.push_subscription import PushSubscription


class PushSubscriptionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert(self, user_id: uuid.UUID, endpoint: str, p256dh_key: str, auth_key: str) -> PushSubscription:
        # endpoint is globally unique (see the model's docstring) - re-subscribing the same
        # browser (e.g. permission was re-granted after being revoked) updates the existing row's
        # keys rather than violating the unique constraint or leaving a stale duplicate.
        result = await self.db.execute(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
        existing = result.scalar_one_or_none()
        if existing:
            existing.user_id = user_id
            existing.p256dh_key = p256dh_key
            existing.auth_key = auth_key
            await self.db.flush()
            return existing
        subscription = PushSubscription(user_id=user_id, endpoint=endpoint, p256dh_key=p256dh_key, auth_key=auth_key)
        self.db.add(subscription)
        await self.db.flush()
        return subscription

    async def list_for_user(self, user_id: uuid.UUID) -> list[PushSubscription]:
        result = await self.db.execute(select(PushSubscription).where(PushSubscription.user_id == user_id))
        return list(result.scalars().all())

    async def delete_by_endpoint(self, endpoint: str) -> None:
        """Unscoped by user_id - called from push_service.py when the push service itself
        reports an endpoint as dead (404/410), which happens outside any particular user's
        request context. The API route below uses delete_for_user instead, which is scoped."""
        await self.db.execute(delete(PushSubscription).where(PushSubscription.endpoint == endpoint))
        await self.db.flush()

    async def delete_for_user(self, user_id: uuid.UUID, endpoint: str) -> None:
        await self.db.execute(
            delete(PushSubscription).where(PushSubscription.endpoint == endpoint, PushSubscription.user_id == user_id)
        )
        await self.db.flush()
