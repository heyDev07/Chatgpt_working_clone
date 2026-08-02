"""Job-application tools: tailor a resume and draft a cover letter against a specific job
description, and (in a later slice) submit an application through a live browser session.

TailorResumeTool/WriteCoverLetterTool are request-scoped like CreateReminderTool/UpsertContactTool
- user_id can't be a model-supplied argument, so it's bound at construction time instead. They
also take provider_manager/provider/model, mirroring the throwaway-LLM-call pattern already used
by classify_agent()/run_title_generation() - each tool call makes its own single, separate
completion rather than participating in the surrounding chat turn's own streamed response.
"""

import uuid
from typing import Any

from app.db.database import async_session_factory
from app.providers.base_provider import ChatMessage
from app.providers.provider_manager import ProviderManager
from app.services.document_service import get_resume_text
from app.tools.base import BaseTool, ToolDefinition

_NO_RESUME_ERROR = (
    "This user hasn't uploaded and marked a resume yet. Ask them to upload one in the Knowledge "
    "base and mark it as their resume before you can tailor it or write a cover letter grounded "
    "in their real background."
)

_TAILOR_SYSTEM_PROMPT = (
    "You tailor resumes to specific job descriptions. Rewrite the given resume so it emphasizes "
    "the experience, skills, and achievements most relevant to the job description, using the "
    "candidate's own real experience only - never invent employers, titles, dates, or skills "
    "that aren't in the original resume. Keep it truthful, concise, and well-organized. Output "
    "only the tailored resume text, no commentary before or after it."
)

_COVER_LETTER_SYSTEM_PROMPT = (
    "You write concise, specific cover letters grounded in the candidate's real resume - never "
    "invent employers, titles, or achievements that aren't in the resume provided. Reference "
    "concrete details from both the resume and the job description rather than generic phrases. "
    "Output only the cover letter text, no commentary before or after it."
)


class TailorResumeTool(BaseTool):
    def __init__(self, user_id: uuid.UUID, provider_manager: ProviderManager, provider: str, model: str):
        self._user_id = user_id
        self._provider_manager = provider_manager
        self._provider = provider
        self._model = model
        self.definition = ToolDefinition(
            name="tailor_resume",
            description=(
                "Rewrites the user's uploaded resume to emphasize what's relevant to a specific "
                "job description. Requires the user to have already uploaded a document and "
                "marked it as their resume (Knowledge base) - fails with a clear error otherwise."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "job_description": {
                        "type": "string",
                        "description": "The job description (or posting text) to tailor the resume for",
                    }
                },
                "required": ["job_description"],
            },
            timeout_seconds=30.0,
        )

    async def run(self, **kwargs: Any) -> dict:
        job_description = kwargs.get("job_description")
        if not isinstance(job_description, str) or not job_description.strip():
            raise ValueError("'job_description' must be a non-empty string")

        async with async_session_factory() as db:
            resume_text = await get_resume_text(db, self._user_id)
        if not resume_text:
            raise ValueError(_NO_RESUME_ERROR)

        provider = self._provider_manager.get_provider(self._provider)
        messages = [
            ChatMessage(role="system", content=_TAILOR_SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=f"Resume:\n{resume_text}\n\nJob description:\n{job_description.strip()}",
            ),
        ]
        result = await provider.generate(messages, self._model, temperature=0.4, max_tokens=1500)
        return {"tailored_resume": result.message.content.strip()}


class WriteCoverLetterTool(BaseTool):
    def __init__(self, user_id: uuid.UUID, provider_manager: ProviderManager, provider: str, model: str):
        self._user_id = user_id
        self._provider_manager = provider_manager
        self._provider = provider
        self._model = model
        self.definition = ToolDefinition(
            name="write_cover_letter",
            description=(
                "Writes a cover letter for a specific job, grounded in the user's uploaded "
                "resume. Requires the user to have already uploaded a document and marked it as "
                "their resume (Knowledge base) - fails with a clear error otherwise."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "job_description": {
                        "type": "string",
                        "description": "The job description (or posting text) to write the cover letter for",
                    },
                    "company_name": {
                        "type": "string",
                        "description": "The company's name, if known - used to address the letter appropriately",
                    },
                },
                "required": ["job_description"],
            },
            timeout_seconds=30.0,
        )

    async def run(self, **kwargs: Any) -> dict:
        job_description = kwargs.get("job_description")
        if not isinstance(job_description, str) or not job_description.strip():
            raise ValueError("'job_description' must be a non-empty string")
        company_name = kwargs.get("company_name")
        company_note = f"Company: {company_name}\n\n" if isinstance(company_name, str) and company_name.strip() else ""

        async with async_session_factory() as db:
            resume_text = await get_resume_text(db, self._user_id)
        if not resume_text:
            raise ValueError(_NO_RESUME_ERROR)

        provider = self._provider_manager.get_provider(self._provider)
        messages = [
            ChatMessage(role="system", content=_COVER_LETTER_SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=f"Resume:\n{resume_text}\n\n{company_note}Job description:\n{job_description.strip()}",
            ),
        ]
        result = await provider.generate(messages, self._model, temperature=0.5, max_tokens=800)
        return {"cover_letter": result.message.content.strip()}
