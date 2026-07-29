from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.config.settings import get_settings
from app.models.user import User
from app.repositories.push_subscription_repo import PushSubscriptionRepository
from app.schemas.push import PushSubscriptionCreate, PushUnsubscribeRequest

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/vapid-public-key")
async def vapid_public_key() -> dict:
    # Public by design (it's a public key) and unauthenticated so the frontend can fetch it
    # before the user necessarily has a session, matching how pushManager.subscribe() needs it
    # available as soon as the permission prompt is shown.
    return {"public_key": get_settings().vapid_public_key}


@router.post("", status_code=201)
async def subscribe(
    payload: PushSubscriptionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await PushSubscriptionRepository(db).upsert(
        current_user.id, payload.endpoint, payload.keys.p256dh, payload.keys.auth
    )
    await db.commit()
    return {"subscribed": True}


@router.post("/unsubscribe", status_code=204)
async def unsubscribe(
    payload: PushUnsubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await PushSubscriptionRepository(db).delete_for_user(current_user.id, payload.endpoint)
    await db.commit()
