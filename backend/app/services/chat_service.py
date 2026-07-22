import uuid
from collections.abc import AsyncIterator

import anyio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ProviderError
from app.models.conversation import Conversation
from app.providers.base_provider import ChatMessage
from app.providers.provider_manager import ProviderManager
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.message_repo import MessageRepository


class ChatService:
    def __init__(self, db: AsyncSession, provider_manager: ProviderManager):
        self.db = db
        self.conversations = ConversationRepository(db)
        self.messages = MessageRepository(db)
        self.provider_manager = provider_manager

    async def get_authorized_conversation(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> Conversation:
        """Must be called (and awaited) before constructing a StreamingResponse - once that
        response starts, headers/status are already committed and a 404 can no longer be sent."""
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if not conversation:
            raise NotFoundError("Conversation not found")
        return conversation

    async def stream_message(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID, content: str
    ) -> AsyncIterator[dict]:
        # Re-fetch within this service's own session rather than accepting an ORM object
        # from the caller: this method is meant to run inside a StreamingResponse generator,
        # which is iterated *after* the route function returns - by then, a request-scoped
        # Depends(get_db) session would already be closed. See get_authorized_conversation.
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if not conversation:
            yield {"event": "error", "data": {"code": "not_found", "message": "Conversation not found"}}
            return

        await self.messages.create(conversation.id, role="user", content=content)
        await self.db.commit()

        history = await self.messages.list_for_conversation(conversation.id)

        if len(history) == 1 and conversation.title == "New Conversation":
            conversation.title = content[:50]
            await self.db.commit()

        provider = self.provider_manager.get_provider(conversation.provider)
        chat_messages = [ChatMessage(role=m.role, content=m.content) for m in history]

        full_content = ""
        finish_reason = "stop"
        usage = None
        error_message: str | None = None

        try:
            async for chunk in provider.stream(chat_messages, conversation.model):
                if chunk.delta:
                    full_content += chunk.delta
                    yield {"event": "token", "data": {"delta": chunk.delta}}
                if chunk.finish_reason:
                    finish_reason = chunk.finish_reason
                if chunk.usage:
                    usage = chunk.usage
        except ProviderError as exc:
            error_message = str(exc)
            finish_reason = "error"
        except (GeneratorExit, anyio.get_cancelled_exc_class()):
            # Client disconnected / stopped generation mid-stream. Starlette's
            # BaseHTTPMiddleware (used by our request-logging middleware) cancels the whole
            # request via a task cancellation on disconnect, not a plain GeneratorExit - so
            # both must be handled the same way here.
            finish_reason = "cancelled"
            raise
        finally:
            assistant_message = None
            if full_content:
                # The cleanup below must run even though the enclosing scope may already be
                # cancelled (client disconnect) - without shielding, these awaits would be
                # cancelled immediately too and the partial reply would never be saved.
                with anyio.CancelScope(shield=True):
                    assistant_message = await self.messages.create(
                        conversation.id,
                        role="assistant",
                        content=full_content,
                        model=conversation.model,
                        finish_reason=finish_reason,
                        token_count=usage.completion_tokens if usage else None,
                    )
                    await self.conversations.touch(conversation)
                    await self.db.commit()

        if error_message:
            yield {"event": "error", "data": {"code": "provider_error", "message": error_message}}
            return

        yield {
            "event": "done",
            "data": {
                "message_id": str(assistant_message.id) if assistant_message else None,
                "finish_reason": finish_reason,
                "usage": (
                    {
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
                        "total_tokens": usage.total_tokens,
                    }
                    if usage
                    else None
                ),
            },
        }
