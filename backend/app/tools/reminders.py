import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.scheduler import schedule_reminder_job
from app.db.database import async_session_factory
from app.repositories.reminder_repo import ReminderRepository
from app.tools.base import BaseTool, ToolDefinition


class CreateReminderTool(BaseTool):
    """Request-scoped, not a shared singleton like calculator/sql_query - the generic
    BaseTool.run(**kwargs) interface only ever receives whatever arguments the LLM supplies, and
    user_id can't be one of those (a model isn't a trustworthy source for whose reminder this
    is). Bound to a specific user/conversation at construction time instead, same pattern
    build_playwright_tools() uses to bind a browser session to one turn - see chat_service.py,
    which constructs one of these fresh per turn and merges it into that turn's registry.

    The current-UTC-time note baked into the description at construction time (not a fixed
    string on the class) is what lets the model compute relative times like "in 20 minutes" or
    "tomorrow at 9am" at all - it has no other way to know what "now" is."""

    def __init__(self, user_id: uuid.UUID, conversation_id: uuid.UUID | None):
        self._user_id = user_id
        self._conversation_id = conversation_id
        now = datetime.now(timezone.utc)
        self.definition = ToolDefinition(
            name="create_reminder",
            description=(
                "Schedules a reminder that will be shown to the user at a future time. "
                f"The current UTC time is {now.isoformat()} - compute remind_at_iso relative to "
                "this when the user gives a relative time (e.g. 'in 20 minutes', 'tomorrow at "
                "9am' - assume the user's tomorrow-9am is also UTC unless they've stated a "
                "timezone elsewhere in the conversation)."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "What to remind the user about, in their own words"},
                    "remind_at_iso": {
                        "type": "string",
                        "description": "ISO 8601 UTC datetime for when to remind them, e.g. 2026-07-27T15:30:00Z",
                    },
                },
                "required": ["message", "remind_at_iso"],
            },
            timeout_seconds=5.0,
        )

    async def run(self, **kwargs: Any) -> dict:
        message = kwargs.get("message")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("'message' must be a non-empty string")

        raw = kwargs.get("remind_at_iso")
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("'remind_at_iso' must be a non-empty ISO 8601 datetime string")
        try:
            remind_at = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"'remind_at_iso' is not a valid ISO 8601 datetime: {exc}") from exc
        if remind_at.tzinfo is None:
            remind_at = remind_at.replace(tzinfo=timezone.utc)
        if remind_at <= datetime.now(timezone.utc):
            raise ValueError("remind_at_iso must be in the future")

        async with async_session_factory() as db:
            reminder = await ReminderRepository(db).create(
                self._user_id, message.strip(), remind_at, self._conversation_id
            )
            await db.commit()
            reminder_id = reminder.id

        schedule_reminder_job(reminder_id, remind_at)
        return {"reminder_id": str(reminder_id), "message": message.strip(), "remind_at": remind_at.isoformat()}
