import re

from app.models.conversation import Conversation

_ROLE_LABELS = {"user": "User", "assistant": "Assistant", "system": "System"}


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "conversation"


def to_markdown(conversation: Conversation) -> str:
    lines = [f"# {conversation.title}", ""]
    for message in conversation.messages:
        speaker = _ROLE_LABELS.get(message.role, message.role)
        lines.append(f"### {speaker}")
        lines.append("")
        lines.append(message.content)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
