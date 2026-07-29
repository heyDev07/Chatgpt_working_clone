"""Gmail/Calendar tools, built on the OAuth credential google_oauth_service.py already proved
works end-to-end (see that module's docstring and app/api/v1/oauth.py's /test endpoint). Read
tools (search/list) use the scopes already granted; the two write tools additionally require
gmail.send/calendar.events, which is why GOOGLE_SCOPES was widened - and both write tools are
marked permission_level="restricted" so tool_loop_graph.py routes them through
app/services/tool_confirmation.py instead of executing unsupervised. Request-scoped like
CreateReminderTool/UpsertContactTool (see chat_service.py) - user_id can't be a model argument.
"""

import base64
import uuid
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import Any

import httpx

from app.db.database import async_session_factory
from app.services.google_oauth_service import GoogleOAuthService
from app.tools.base import BaseTool, ToolDefinition

GMAIL_MESSAGES_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


async def _get_access_token(user_id: uuid.UUID) -> str:
    async with async_session_factory() as db:
        return await GoogleOAuthService(db).get_valid_access_token(user_id)


class SearchGmailTool(BaseTool):
    def __init__(self, user_id: uuid.UUID):
        self._user_id = user_id
        self.definition = ToolDefinition(
            name="search_gmail",
            description=(
                "Searches the user's Gmail inbox and returns matching messages (subject, "
                "sender, date, snippet). Uses Gmail's own search syntax (e.g. 'from:someone', "
                "'is:unread', 'subject:invoice') - a plain query also works as a general search. "
                "Requires the user to have connected their Google account in Settings."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Gmail search query, e.g. 'is:unread' or 'from:boss@company.com'"},
                    "max_results": {"type": "integer", "description": "Max messages to return (default 5, max 10)"},
                },
                "required": ["query"],
            },
            timeout_seconds=15.0,
        )

    async def run(self, **kwargs: Any) -> dict:
        query = kwargs.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("'query' must be a non-empty string")
        max_results = min(int(kwargs.get("max_results") or 5), 10)

        access_token = await _get_access_token(self._user_id)
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            list_response = await client.get(
                GMAIL_MESSAGES_URL, headers=headers, params={"q": query, "maxResults": max_results}
            )
            list_response.raise_for_status()
            message_ids = [m["id"] for m in list_response.json().get("messages", [])]

            messages = []
            for message_id in message_ids:
                detail_response = await client.get(
                    f"{GMAIL_MESSAGES_URL}/{message_id}",
                    headers=headers,
                    params={"format": "metadata", "metadataHeaders": ["Subject", "From", "Date"]},
                )
                detail_response.raise_for_status()
                data = detail_response.json()
                header_map = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}
                messages.append(
                    {
                        "id": message_id,
                        "subject": header_map.get("Subject"),
                        "from": header_map.get("From"),
                        "date": header_map.get("Date"),
                        "snippet": data.get("snippet"),
                    }
                )
        return {"messages": messages}


class ListCalendarEventsTool(BaseTool):
    def __init__(self, user_id: uuid.UUID):
        self._user_id = user_id
        self.definition = ToolDefinition(
            name="list_calendar_events",
            description=(
                "Lists the user's upcoming Google Calendar events (title, start/end time, "
                "location). Requires the user to have connected their Google account in Settings."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "max_results": {"type": "integer", "description": "Max events to return (default 10, max 20)"},
                },
            },
            timeout_seconds=15.0,
        )

    async def run(self, **kwargs: Any) -> dict:
        max_results = min(int(kwargs.get("max_results") or 10), 20)
        access_token = await _get_access_token(self._user_id)

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                CALENDAR_EVENTS_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "maxResults": max_results,
                    "orderBy": "startTime",
                    "singleEvents": "true",
                    "timeMin": datetime.now(timezone.utc).isoformat(),
                },
            )
            response.raise_for_status()
            items = response.json().get("items", [])

        events = [
            {
                "summary": item.get("summary"),
                "start": item.get("start", {}).get("dateTime") or item.get("start", {}).get("date"),
                "end": item.get("end", {}).get("dateTime") or item.get("end", {}).get("date"),
                "location": item.get("location"),
            }
            for item in items
        ]
        return {"events": events}


class SendGmailTool(BaseTool):
    def __init__(self, user_id: uuid.UUID):
        self._user_id = user_id
        self.definition = ToolDefinition(
            name="send_gmail",
            description=(
                "Sends an email from the user's Gmail account. The user must explicitly approve "
                "this before it actually sends - always tell the user what you're about to send "
                "and why before calling this, so the approval prompt isn't their first look at it."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string"},
                    "body": {"type": "string", "description": "Plain-text email body"},
                },
                "required": ["to", "subject", "body"],
            },
            permission_level="restricted",
            timeout_seconds=15.0,
        )

    async def run(self, **kwargs: Any) -> dict:
        to = kwargs.get("to")
        subject = kwargs.get("subject")
        body = kwargs.get("body")
        if not isinstance(to, str) or not to.strip():
            raise ValueError("'to' must be a non-empty string")
        if not isinstance(subject, str):
            raise ValueError("'subject' must be a string")
        if not isinstance(body, str):
            raise ValueError("'body' must be a string")

        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        access_token = await _get_access_token(self._user_id)
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{GMAIL_MESSAGES_URL}/send",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"raw": raw},
            )
            response.raise_for_status()
            data = response.json()
        return {"message_id": data.get("id"), "to": to, "subject": subject}


class CreateCalendarEventTool(BaseTool):
    def __init__(self, user_id: uuid.UUID):
        self._user_id = user_id
        self.definition = ToolDefinition(
            name="create_calendar_event",
            description=(
                "Creates an event on the user's Google Calendar. The user must explicitly "
                "approve this before it's actually created - always tell the user the event "
                "details before calling this, so the approval prompt isn't their first look."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Event title"},
                    "start_iso": {"type": "string", "description": "ISO 8601 start datetime, e.g. 2026-08-01T15:00:00Z"},
                    "end_iso": {"type": "string", "description": "ISO 8601 end datetime"},
                    "location": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["summary", "start_iso", "end_iso"],
            },
            permission_level="restricted",
            timeout_seconds=15.0,
        )

    async def run(self, **kwargs: Any) -> dict:
        summary = kwargs.get("summary")
        start_iso = kwargs.get("start_iso")
        end_iso = kwargs.get("end_iso")
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("'summary' must be a non-empty string")
        if not isinstance(start_iso, str) or not isinstance(end_iso, str):
            raise ValueError("'start_iso' and 'end_iso' must be ISO 8601 datetime strings")

        event_body: dict[str, Any] = {
            "summary": summary,
            "start": {"dateTime": start_iso},
            "end": {"dateTime": end_iso},
        }
        location = kwargs.get("location")
        if isinstance(location, str) and location.strip():
            event_body["location"] = location
        description = kwargs.get("description")
        if isinstance(description, str) and description.strip():
            event_body["description"] = description

        access_token = await _get_access_token(self._user_id)
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                CALENDAR_EVENTS_URL, headers={"Authorization": f"Bearer {access_token}"}, json=event_body
            )
            response.raise_for_status()
            data = response.json()
        return {"event_id": data.get("id"), "summary": summary, "html_link": data.get("htmlLink")}
