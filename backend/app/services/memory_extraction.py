import logging
import re
import uuid
from difflib import SequenceMatcher

from app.db.database import async_session_factory
from app.providers.base_provider import ChatMessage
from app.providers.provider_manager import ProviderManager
from app.repositories.memory_repo import MemoryRepository

logger = logging.getLogger("app.memory_extraction")

VALID_CATEGORIES = {"preference", "project", "goal", "communication_style", "general"}

# Above this, a newly extracted memory is treated as a restatement of an existing one rather than
# a new fact - found via real duplicates in production data ("Prefers concise, direct answers
# without fluff." stored 4 separate times from 4 different conversations that each happened to
# touch on the same preference). SequenceMatcher over lowercased text is a cheap, dependency-free
# stand-in for real semantic similarity - good enough for near-restatements, which is what this
# app's actual duplicates look like, though it won't catch two sentences that say the same thing
# in genuinely different words.
_DUPLICATE_SIMILARITY_THRESHOLD = 0.8

_EXTRACTION_SYSTEM_PROMPT = """You analyze a single chat exchange and decide whether it reveals a \
durable fact worth remembering about the user long-term: preferences, ongoing projects, recurring \
goals, or communication style.

Do NOT extract: secrets or credentials, one-off requests, small talk, or anything that isn't clearly \
a lasting fact about the user themselves. In particular, a one-off instruction that only applies to \
the current message (e.g. "answer in exactly three words", "keep this one short") is NOT a durable \
communication-style preference unless the user has explicitly said they want you to behave that way \
going forward, every time.

If nothing is worth storing, respond with exactly: NONE

Otherwise respond with exactly one line in this format (no other text):
CATEGORY: <preference|project|goal|communication_style|general> | IMPORTANCE: <0.0-1.0> | TEXT: <one sentence, third person, about the user>
"""

_RESULT_PATTERN = re.compile(
    r"CATEGORY:\s*(?P<category>\w+)\s*\|\s*IMPORTANCE:\s*(?P<importance>[0-9.]+)\s*\|\s*TEXT:\s*(?P<text>.+)",
    re.IGNORECASE | re.DOTALL,
)


async def run_memory_extraction(
    provider_manager: ProviderManager,
    user_id: uuid.UUID,
    provider_name: str,
    model_name: str,
    user_text: str,
    assistant_text: str,
) -> None:
    """Fire-and-forget: analyzes one exchange and stores a memory if warranted. Never raises -
    this must not be able to break the user-facing chat flow it's triggered from."""
    try:
        provider = provider_manager.get_provider(provider_name)
        messages = [
            ChatMessage(role="system", content=_EXTRACTION_SYSTEM_PROMPT),
            ChatMessage(role="user", content=f"User: {user_text}\nAssistant: {assistant_text}"),
        ]
        result = await provider.generate(messages, model_name, temperature=0.2, max_tokens=150)
        raw = result.message.content.strip()

        if not raw or raw.strip().upper().startswith("NONE"):
            return

        match = _RESULT_PATTERN.search(raw)
        if not match:
            logger.info("Memory extraction: unparseable response, skipping: %r", raw[:200])
            return

        category = match.group("category").lower()
        if category not in VALID_CATEGORIES:
            category = "general"

        try:
            importance = max(0.0, min(1.0, float(match.group("importance"))))
        except ValueError:
            importance = 0.5

        text = match.group("text").strip()
        if not text:
            return

        async with async_session_factory() as db:
            memories = MemoryRepository(db)
            existing = await memories.list_for_user(user_id)
            normalized = text.lower()
            if any(
                SequenceMatcher(None, normalized, m.memory_text.lower()).ratio() >= _DUPLICATE_SIMILARITY_THRESHOLD
                for m in existing
            ):
                return
            await memories.create(user_id, category, text, importance)
            await db.commit()
    except Exception:
        logger.exception("Memory extraction failed for user %s", user_id)
