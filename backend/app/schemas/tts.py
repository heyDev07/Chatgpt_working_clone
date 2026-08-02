from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    # One sentence at a time in practice (see voiceMode.ts's chunker), but no hard reason to
    # forbid a longer passage - capped well above a normal sentence to bound worst-case latency
    # and Gemini request size, not because anything shorter is invalid.
    text: str = Field(min_length=1, max_length=2000)
    voice: str | None = None
