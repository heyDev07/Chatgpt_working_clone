"""Web Push (VAPID) - what actually makes reminders show up as a real OS notification even when
the tab isn't open, unlike ReminderBell.tsx's 20s poll which only works while the page is loaded.
pywebpush handles the aes128gcm payload encryption and VAPID JWT signing (a well-tested, focused
library for a genuinely fiddly bit of crypto - not the kind of "heavy SDK" this project otherwise
avoids, more comparable to argon2-cffi for password hashing than to something like
google-api-python-client).
"""

import json
import logging
import uuid

from pywebpush import WebPushException, webpush
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.repositories.push_subscription_repo import PushSubscriptionRepository

logger = logging.getLogger("app.push")


async def send_push_notification(db: AsyncSession, user_id: uuid.UUID, title: str, body: str) -> None:
    """Best-effort fan-out to every subscription this user has (one per browser/device they've
    granted permission on - see PushSubscription's docstring). A failure to push is never allowed
    to break the caller's own flow (e.g. a reminder still gets marked delivered for the in-app
    poll even if every push attempt fails) - logged, not raised."""
    settings = get_settings()
    if not settings.vapid_private_key:
        return  # push not configured on this server - graceful no-op, same as every other optional integration

    repo = PushSubscriptionRepository(db)
    subscriptions = await repo.list_for_user(user_id)
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh_key, "auth": sub.auth_key},
                },
                data=json.dumps({"title": title, "body": body}),
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": f"mailto:{settings.vapid_admin_email}"},
            )
        except WebPushException as exc:
            status_code = getattr(exc.response, "status_code", None)
            if status_code in (404, 410):
                # The browser unsubscribed or the subscription otherwise expired - the push
                # service itself is telling us this endpoint will never accept another push, so
                # clean it up rather than retrying it forever on every future reminder.
                await repo.delete_by_endpoint(sub.endpoint)
                await db.commit()
            else:
                logger.warning("Push to %s failed: %s", sub.endpoint, exc)
        except Exception:
            # webpush() can fail below its own WebPushException layer too - DNS/connection errors
            # for an endpoint that's unreachable or was never a real push service to begin with.
            # One subscriber's broken endpoint must never stop the loop from reaching the rest.
            logger.exception("Unexpected error pushing to %s", sub.endpoint)
