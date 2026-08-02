"""Job-application tools: tailor a resume and draft a cover letter against a specific job
description, and submit an application through a live browser session.

TailorResumeTool/WriteCoverLetterTool are request-scoped like CreateReminderTool/UpsertContactTool
- user_id can't be a model-supplied argument, so it's bound at construction time instead. They
also take provider_manager/provider/model, mirroring the throwaway-LLM-call pattern already used
by classify_agent()/run_title_generation() - each tool call makes its own single, separate
completion rather than participating in the surrounding chat turn's own streamed response.

SubmitJobApplicationTool is permission_level="restricted" (see tool_confirmation.py/
tool_loop_graph.py's call_tools_node) - deliberately the *only* way this agent persona can ever
submit a form. The job_application persona (app/agents/definitions.py) is given browser_navigate/
browser_snapshot but none of the raw interaction tools (browser_click/type/fill_form), so there is
exactly one confirmable action per application, not several small unconfirmed browser steps that
add up to the same effect.
"""

import json
import uuid
from typing import Any

from app.db.database import async_session_factory
from app.db.redis_client import get_redis
from app.middleware.rate_limit import job_application_rate_limiter
from app.providers.base_provider import ChatMessage
from app.providers.provider_manager import ProviderManager
from app.services.document_service import get_resume_text
from app.tools.base import BaseTool, ToolDefinition
from app.tools.browser import PlaywrightBrowserSession

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


_FILL_PLAN_SYSTEM_PROMPT = (
    "You map a job application form's real fields (from an accessibility snapshot) to an "
    "applicant's information. Respond with ONLY strict JSON, no markdown code fences, no "
    "commentary - exactly this shape: "
    '{"fields": [{"target": "<exact ref from the snapshot, e.g. e11>", "name": "<human field '
    'name>", "type": "textbox"|"checkbox"|"radio"|"combobox"|"slider", "value": "<value to '
    'fill>"}], "submit_target": "<exact ref of the submit/apply button>"}. '
    "Only include fields that clearly correspond to one of: full name, email, phone, resume "
    "text, or cover letter text - skip fields you can't confidently map (disabled/readonly "
    "inputs, unrelated dropdowns) rather than guessing. Use the exact ref values as they appear "
    "in the snapshot (e.g. 'e11'), never a description in their place."
)


class SubmitJobApplicationTool(BaseTool):
    """The one restricted, consequential action in this whole feature - see the module
    docstring for why every other job-application capability stops short of this. Takes a live
    PlaywrightBrowserSession (constructed per-turn in chat_service.py, same object build_
    playwright_tools() wraps the generic browser_* tools around) rather than driving its own -
    Playwright's tools only make sense against the one open tab a turn already has."""

    def __init__(
        self,
        user_id: uuid.UUID,
        session: PlaywrightBrowserSession,
        provider_manager: ProviderManager,
        provider: str,
        model: str,
    ):
        self._user_id = user_id
        self._session = session
        self._provider_manager = provider_manager
        self._provider = provider
        self._model = model
        self.definition = ToolDefinition(
            name="submit_job_application",
            description=(
                "Fills out and submits a real job application form at the given URL using the "
                "applicant's real information. This is a real, consequential action - always "
                "tell the user which job you're about to apply to and exactly what you're "
                "submitting (the resume and cover letter content) before calling this, so the "
                "approval prompt they'll see isn't their first look at it."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "job_url": {"type": "string", "description": "URL of the job application page to submit"},
                    "applicant_name": {"type": "string", "description": "The applicant's full name"},
                    "applicant_email": {"type": "string", "description": "The applicant's email address"},
                    "applicant_phone": {
                        "type": "string",
                        "description": "The applicant's phone number, or an empty string if not applicable",
                    },
                    "resume_text": {
                        "type": "string",
                        "description": "The (ideally tailored) resume text to submit",
                    },
                    "cover_letter_text": {
                        "type": "string",
                        "description": "The cover letter text to submit, or an empty string if the form has no such field",
                    },
                },
                "required": ["job_url", "applicant_name", "applicant_email", "resume_text"],
            },
            permission_level="restricted",
            timeout_seconds=90.0,
        )

    async def _build_fill_plan(
        self,
        snapshot_text: str,
        applicant_name: str,
        applicant_email: str,
        applicant_phone: str,
        resume_text: str,
        cover_letter_text: str,
    ) -> dict:
        provider = self._provider_manager.get_provider(self._provider)
        candidate_info = (
            f"Full name: {applicant_name}\n"
            f"Email: {applicant_email}\n"
            f"Phone: {applicant_phone or '(not provided)'}\n\n"
            f"Resume text:\n{resume_text}\n\n"
            f"Cover letter text:\n{cover_letter_text or '(not provided)'}"
        )
        messages = [
            ChatMessage(role="system", content=_FILL_PLAN_SYSTEM_PROMPT),
            ChatMessage(role="user", content=f"Page snapshot:\n{snapshot_text}\n\nApplicant info:\n{candidate_info}"),
        ]
        result = await provider.generate(messages, self._model, temperature=0.0, max_tokens=1200)
        raw = result.message.content.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[len("json") :]
        try:
            plan = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Could not read the application form's fields from the page: {exc}") from exc
        if not isinstance(plan, dict):
            raise ValueError("Could not read the application form's fields from the page")
        return plan

    async def run(self, **kwargs: Any) -> dict:
        job_url = kwargs.get("job_url")
        if not isinstance(job_url, str) or not job_url.strip():
            raise ValueError("'job_url' must be a non-empty string")
        applicant_name = kwargs.get("applicant_name")
        if not isinstance(applicant_name, str) or not applicant_name.strip():
            raise ValueError("'applicant_name' must be a non-empty string")
        applicant_email = kwargs.get("applicant_email")
        if not isinstance(applicant_email, str) or not applicant_email.strip():
            raise ValueError("'applicant_email' must be a non-empty string")
        resume_text = kwargs.get("resume_text")
        if not isinstance(resume_text, str) or not resume_text.strip():
            raise ValueError("'resume_text' must be a non-empty string")
        applicant_phone = kwargs.get("applicant_phone") or ""
        cover_letter_text = kwargs.get("cover_letter_text") or ""

        # Independent of the confirmation this call already required - a cap on top of "was this
        # one approved", not a substitute for it (see rate_limit.py's comment on this limiter).
        await job_application_rate_limiter.check(get_redis(), identifier=str(self._user_id))

        await self._session.call_tool("browser_navigate", {"url": job_url.strip()})
        snapshot = await self._session.call_tool("browser_snapshot", {})
        snapshot_text = snapshot if isinstance(snapshot, str) else str(snapshot)

        plan = await self._build_fill_plan(
            snapshot_text, applicant_name, applicant_email, applicant_phone, resume_text, cover_letter_text
        )
        fields = plan.get("fields")
        submit_target = plan.get("submit_target")
        if not isinstance(fields, list) or not fields:
            raise ValueError(f"Could not identify any fillable fields on the application form at {job_url}")
        if not isinstance(submit_target, str) or not submit_target:
            raise ValueError(f"Could not identify a submit button on the application form at {job_url}")

        await self._session.call_tool("browser_fill_form", {"fields": fields})
        await self._session.call_tool(
            "browser_click", {"target": submit_target, "element": "Submit application button"}
        )
        confirmation = await self._session.call_tool("browser_snapshot", {})

        return {
            "job_url": job_url.strip(),
            "submitted": True,
            "confirmation_page": confirmation if isinstance(confirmation, str) else str(confirmation),
        }
