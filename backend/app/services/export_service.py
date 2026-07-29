import re

from fpdf import FPDF

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


def to_pdf(conversation: Conversation) -> bytes:
    # fpdf2, not weasyprint/reportlab - no system-level deps (weasyprint needs Cairo/Pango
    # installed on the host) for what's fundamentally simple text layout, matching this project's
    # preference for the smallest tool that does the job (same reasoning kept Web Push on
    # pywebpush rather than a full notification-service SDK).
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # latin-1 is fpdf2's core-font encoding ceiling - replacing anything outside it keeps export
    # from hard-crashing on an emoji or non-Latin character somewhere in the conversation, at the
    # cost of that one character rendering as "?" rather than correctly. An embedded Unicode TTF
    # font would fix this properly; more than a transcript export needs right now.
    def latin1(text: str) -> str:
        return text.encode("latin-1", "replace").decode("latin-1")

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, latin1(conversation.title), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    for message in conversation.messages:
        speaker = _ROLE_LABELS.get(message.role, message.role)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, speaker, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, latin1(message.content))
        pdf.ln(3)

    return bytes(pdf.output())
