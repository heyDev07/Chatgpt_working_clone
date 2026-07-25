import json
import uuid
from typing import Any
from urllib.parse import quote

import httpx

from app.storage.s3_client import upload_bytes
from app.tools.base import BaseTool, ToolDefinition

POLLINATIONS_TIMEOUT_SECONDS = 45.0
_CONTENT_TYPE_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


class GenerateImageTool(BaseTool):
    definition = ToolDefinition(
        name="generate_image",
        description=(
            "Generates a new image from a text description and includes it in the reply. Use "
            "this when the user asks to create, draw, generate, or make an image - not for "
            "describing an image the user already uploaded, which is handled automatically."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "A detailed description of the image to generate",
                }
            },
            "required": ["prompt"],
        },
        permission_level="public",
        timeout_seconds=POLLINATIONS_TIMEOUT_SECONDS,
    )

    async def run(self, **kwargs: Any) -> str:
        prompt = kwargs.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("'prompt' must be a non-empty string")

        # Pollinations.ai: a keyless, free hosted text-to-image API - a plain GET against a
        # fixed, trusted host with the prompt URL-encoded into the path returns raw image bytes
        # directly, no auth, no request body. Chosen over a local diffusion model (FLUX/SDXL):
        # those need multi-GB downloads and a real GPU to run at usable speed, neither of which
        # this deployment has - this is the same "don't build infra you can't verify works well"
        # tradeoff as everything else in this project.
        url = f"https://image.pollinations.ai/prompt/{quote(prompt.strip())}"
        async with httpx.AsyncClient(timeout=POLLINATIONS_TIMEOUT_SECONDS) as client:
            response = await client.get(url, params={"nologo": "true"})
            response.raise_for_status()
            data = response.content
            content_type = response.headers.get("content-type", "").split(";")[0].strip()

        if not content_type.startswith("image/"):
            raise ValueError(f"Image generation service returned unexpected content-type '{content_type}'")

        extension = _CONTENT_TYPE_EXTENSIONS.get(content_type, "jpg")
        storage_key = f"generated/{uuid.uuid4()}.{extension}"
        await upload_bytes(storage_key, data, content_type)

        # Read by both the LLM (so it knows generation succeeded and can describe the image) and
        # chat_service (which parses this same JSON back out after the tool loop to actually
        # attach the image to the persisted assistant message) - the tool itself has no DB access
        # and doesn't need any, matching every other tool's minimal dependency footprint.
        return json.dumps(
            {
                "generated": True,
                "storage_key": storage_key,
                "content_type": content_type,
                "size_bytes": len(data),
                "filename": f"generated-image.{extension}",
            }
        )
