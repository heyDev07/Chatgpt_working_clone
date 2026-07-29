"""Reminders are this app's first genuinely *recurring/scheduled* background work - everything
before this (title generation, memory extraction, document processing) is fire-once work
triggered by a request, handled with a plain asyncio.create_task() and none the worse for it.
"Run this again automatically at a specific future time, independent of any request, and survive
a restart" needs an actual scheduler; asyncio.create_task() alone has no notion of "later."

APScheduler's AsyncIOScheduler runs coroutine jobs on this process's own event loop - no separate
worker process needed, matching this app's existing preference for the lightest tool that
actually fits the need (the same reasoning that kept document processing off Celery). Its
SQLAlchemyJobStore is what makes scheduled jobs survive a restart (job definitions persisted in
Postgres, not just held in memory) - but that job store is not async-native: internally it uses
plain synchronous SQLAlchemy Core table operations, confirmed by reading its actual source
(SQLAlchemyJobStore.start() calls self.jobs_t.create(self.engine, True), a sync Core call) rather
than assumed from docs. It cannot share this app's asyncpg-based async engine, so it gets its own
dedicated psycopg2 (sync) engine here, used for nothing except APScheduler's own bookkeeping
table (apscheduler_jobs) - completely separate from every other table in this app, all of which
go through the async engine in app/db/database.py as normal.
"""

import logging
import uuid
from datetime import datetime

from apscheduler.jobstores.base import JobLookupError
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config.settings import get_settings
from app.db.database import async_session_factory
from app.repositories.reminder_repo import ReminderRepository
from app.services.push_service import send_push_notification

logger = logging.getLogger("app.scheduler")

_JOB_ID_PREFIX = "reminder:"


def _sync_database_url() -> str:
    # settings.database_url is postgresql+asyncpg://... for the app's real async engine -
    # SQLAlchemyJobStore needs a plain sync driver instead (psycopg2, installed specifically for
    # this). Swapping the driver qualifier, not the host/credentials/db name, so this always
    # points at the exact same database as everything else.
    settings = get_settings()
    return settings.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


scheduler = AsyncIOScheduler(
    jobstores={"default": SQLAlchemyJobStore(url=_sync_database_url(), tablename="apscheduler_jobs")},
    timezone="UTC",
)


async def _deliver_reminder(reminder_id: str) -> None:
    """The job body APScheduler actually runs at remind_at. Marks the row delivered (what
    GET /reminders?due=true polls for - see ReminderBell.tsx) and, separately, fans out a real
    Web Push notification to every device the user has granted permission on (see
    push_service.py) - that's what surfaces a reminder even when no tab is open, which polling
    alone can never do. The two are independent: a push failure (or push simply not being
    configured) must never stop the row from being marked delivered for the in-app path."""
    try:
        async with async_session_factory() as db:
            repo = ReminderRepository(db)
            reminder = await repo.mark_delivered(uuid.UUID(reminder_id))
            await db.commit()
            if reminder is not None:
                await send_push_notification(db, reminder.user_id, "Reminder", reminder.message)
    except Exception:
        logger.exception("Failed to mark reminder %s delivered", reminder_id)


def schedule_reminder_job(reminder_id: uuid.UUID, remind_at: datetime) -> None:
    scheduler.add_job(
        _deliver_reminder,
        trigger="date",
        run_date=remind_at,
        args=[str(reminder_id)],
        id=f"{_JOB_ID_PREFIX}{reminder_id}",
        replace_existing=True,
        misfire_grace_time=None,  # fire immediately on catch-up if the app was down past remind_at, never just drop it
    )


def cancel_reminder_job(reminder_id: uuid.UUID) -> None:
    # A "date"-trigger job removes itself from the store once it fires - deleting a reminder
    # that's already been delivered (or is delivering right now) hits that as a normal case, not
    # an error the caller needs to handle.
    try:
        scheduler.remove_job(f"{_JOB_ID_PREFIX}{reminder_id}", jobstore="default")
    except JobLookupError:
        pass
