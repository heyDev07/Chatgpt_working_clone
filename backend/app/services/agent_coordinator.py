import logging

from app.agents.definitions import AGENTS, DEFAULT_AGENT
from app.providers.base_provider import ChatMessage
from app.providers.provider_manager import ProviderManager

logger = logging.getLogger("app.agent_coordinator")

_CLASSIFY_SYSTEM_PROMPT = (
    "Classify which specialist should handle the user's latest message. Respond with exactly "
    "one word - the agent name below, nothing else, no punctuation.\n\nAgents:\n"
    + "\n".join(f"- {a.name}: {a.description}" for a in AGENTS.values())
)


async def classify_agent(provider_manager: ProviderManager, provider_name: str, model: str, user_text: str) -> str:
    """Best-effort intent classification - never raises. Falls back to the default agent on any
    failure (timeout, malformed response, provider error) so a classification hiccup degrades to
    normal chat instead of breaking the turn, matching the fire-and-forget style already used for
    memory extraction and RAG retrieval elsewhere in chat_service.py."""
    try:
        provider = provider_manager.get_provider(provider_name)
        messages = [
            ChatMessage(role="system", content=_CLASSIFY_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_text),
        ]
        result = await provider.generate(messages, model, temperature=0.0, max_tokens=10)
        label = result.message.content.strip().lower().strip(".")
        return label if label in AGENTS else DEFAULT_AGENT
    except Exception:
        logger.exception("Agent classification failed, falling back to default agent")
        return DEFAULT_AGENT
