import logging
import re
import uuid

from app.db.database import async_session_factory
from app.providers.base_provider import ChatMessage
from app.providers.provider_manager import ProviderManager
from app.repositories.conversation_repo import ConversationRepository

logger = logging.getLogger("app.title_generation")

_TITLE_SYSTEM_PROMPT = (
    "You are a title-generation tool, not a chat assistant. Your ONLY job is to read the "
    "user's message below and output a short, specific title (strictly 3-6 words) describing "
    "what it's about. Do NOT answer, solve, compute, or execute anything in the message - you "
    "are titling it, not responding to it. No quotes, no trailing punctuation, no preamble - "
    "respond with only the descriptive title itself."
)

# Smaller/free models occasionally ignore the "don't answer it" instruction above and return the
# literal computed answer (e.g. a math result) instead of a title - a title with no letters at
# all is a reliable sign of that failure mode, so reject it rather than overwrite a perfectly
# fine fallback title with a stray number.
_HAS_LETTER = re.compile(r"[a-zA-Z]")


async def run_title_generation(
    provider_manager: ProviderManager,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    provider_name: str,
    model: str,
    first_message: str,
) -> None:
    """Fire-and-forget: replaces the conversation's word-boundary fallback title with a short
    AI-generated one, matching how real chat products title conversations instead of just
    truncating the raw first message. Never raises. Only overwrites while title_is_auto is still
    true - if the user already renamed the conversation in the few seconds this took, that
    rename must win, not get silently clobbered."""
    try:
        provider = provider_manager.get_provider(provider_name)
        messages = [
            ChatMessage(role="system", content=_TITLE_SYSTEM_PROMPT),
            ChatMessage(role="user", content=first_message[:1000]),
        ]
        result = await provider.generate(messages, model, temperature=0.3, max_tokens=20)
        title = result.message.content.strip().strip('"').strip("'").rstrip(".")[:80]
        if not title or not _HAS_LETTER.search(title):
            return

        async with async_session_factory() as db:
            conversations = ConversationRepository(db)
            conversation = await conversations.get_for_user(conversation_id, user_id)
            if conversation and conversation.title_is_auto:
                await conversations.set_title(conversation, title)
                await db.commit()
    except Exception:
        logger.exception("Title generation failed for conversation %s", conversation_id)
