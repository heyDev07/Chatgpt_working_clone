import uuid
from datetime import datetime, timezone
from typing import Any

from app.db.database import async_session_factory
from app.services.contact_service import ContactService
from app.tools.base import BaseTool, ToolDefinition


class UpsertContactTool(BaseTool):
    """Request-scoped like CreateReminderTool (see chat_service.py) - user_id can't be a model
    argument, so this is bound to a specific user at construction time and merged into every
    turn's registry rather than registered as a shared singleton."""

    def __init__(self, user_id: uuid.UUID):
        self._user_id = user_id
        self.definition = ToolDefinition(
            name="upsert_contact",
            description=(
                "Remembers or updates a note about a person the user mentions (coworker, "
                "friend, family member, etc). Same-name contacts are merged automatically - "
                "calling this again for a name that already exists appends the new note rather "
                "than replacing what's already known about them, and updates relationship/"
                "last_contact_at if given. Use this whenever the user shares something worth "
                "remembering about a specific named person, not for one-off facts unrelated to "
                "a person."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The person's name"},
                    "relationship": {
                        "type": "string",
                        "description": "How this person relates to the user, e.g. 'manager', 'college friend', 'sister'",
                    },
                    "note": {
                        "type": "string",
                        "description": "What to remember about them from this conversation",
                    },
                },
                "required": ["name"],
            },
            timeout_seconds=5.0,
        )

    async def run(self, **kwargs: Any) -> dict:
        name = kwargs.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("'name' must be a non-empty string")
        relationship = kwargs.get("relationship")
        if relationship is not None and not isinstance(relationship, str):
            raise ValueError("'relationship' must be a string")
        note = kwargs.get("note")
        if note is not None and not isinstance(note, str):
            raise ValueError("'note' must be a string")

        async with async_session_factory() as db:
            contact = await ContactService(db).upsert(
                self._user_id,
                name.strip(),
                relationship.strip() if relationship else None,
                note.strip() if note else None,
                datetime.now(timezone.utc),
            )
            return {
                "contact_id": str(contact.id),
                "name": contact.name,
                "relationship": contact.relationship,
                "notes": contact.notes,
            }


class ListContactsTool(BaseTool):
    """Request-scoped for the same reason as UpsertContactTool - a list of contacts is always
    scoped to the requesting user, never something the model can be trusted to filter itself."""

    def __init__(self, user_id: uuid.UUID):
        self._user_id = user_id
        self.definition = ToolDefinition(
            name="list_contacts",
            description=(
                "Lists people the user has previously told the assistant about, with whatever "
                "relationship and notes have been recorded for each. Use this when the user "
                "asks something like 'who is X' or 'what do you know about my contacts'."
            ),
            input_schema={"type": "object", "properties": {}},
            timeout_seconds=5.0,
        )

    async def run(self, **kwargs: Any) -> dict:
        async with async_session_factory() as db:
            contacts = await ContactService(db).list_for_user(self._user_id)
            return {
                "contacts": [
                    {
                        "name": c.name,
                        "relationship": c.relationship,
                        "notes": c.notes,
                        "last_contact_at": c.last_contact_at.isoformat() if c.last_contact_at else None,
                    }
                    for c in contacts
                ]
            }
