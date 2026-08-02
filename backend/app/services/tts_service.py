"""Text-to-speech via Gemini's native TTS models - a dedicated module rather than a method on
GeminiProvider/BaseProvider, since this is a fundamentally different call shape (text -> audio
bytes, not chat messages -> text) and is Gemini-only for now: OpenRouter (the app's "openai"
provider slot, see openai_provider.py) doesn't proxy /audio/* endpoints, and forcing this onto
BaseProvider's abstract interface would make every other provider stub a capability it can't
offer - the same reasoning embedding_provider already exists as its own separate setting instead
of living on generate(). Powers Slice 2's voice mode: one call per sentence, not per turn.

Gemini's TTS response is raw headerless PCM (confirmed live: mime_type
"audio/L16;codec=pcm;rate=24000", not any playable container) - browsers can't play that
directly via <audio>, so _wrap_pcm_as_wav() adds a standard 44-byte WAV header before this ever
reaches the client. Verified end-to-end by writing the wrapped bytes to a real .wav file and
reading it back with Python's own `wave` module.
"""

import asyncio
import re
import struct

from google import genai
from google.genai import types

from app.config.settings import get_settings
from app.core.exceptions import ProviderError

TTS_MODEL = "gemini-2.5-flash-preview-tts"
DEFAULT_VOICE = "Kore"

_RATE_PATTERN = re.compile(r"rate=(\d+)")

# Reproduced live during implementation: an occasional transient connection failure deep in the
# SDK's aiohttp transport (ClientPayloadError wrapping a plain ConnectionResetError) - the same
# class of intermittent network issue diagnosed elsewhere in this project (see http_retry.py),
# just surfacing through a different transport library here. GeminiProvider's own
# _call_with_retry only retries a 429 ClientError, which would NOT have caught this (confirmed:
# it's a raw connection error, not a rate-limit response), so this needs its own broader retry
# rather than reusing that one. 3/3 immediate retries succeeded when reproducing this, so a short
# fixed cap is enough - no elaborate backoff needed for something this rare.
_MAX_ATTEMPTS = 3


def _wrap_pcm_as_wav(pcm_data: bytes, sample_rate: int, channels: int = 1, bits_per_sample: int = 16) -> bytes:
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(pcm_data),
        b"WAVE",
        b"fmt ",
        16,
        1,  # PCM
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        len(pcm_data),
    )
    return header + pcm_data


async def synthesize_speech(text: str, voice: str = DEFAULT_VOICE) -> bytes:
    """Returns playable WAV bytes for the given text. Never returns raw PCM - every caller
    (the /tts endpoint, and nothing else today) gets browser-playable audio directly."""
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)

    config = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice))
        ),
    )

    last_exc: Exception | None = None
    response = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            response = await client.aio.models.generate_content(model=TTS_MODEL, contents=text, config=config)
            break
        except Exception as exc:
            last_exc = exc
            if attempt < _MAX_ATTEMPTS - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
    if response is None:
        raise ProviderError(f"Gemini TTS failed: {last_exc}") from last_exc

    candidates = response.candidates or []
    parts = candidates[0].content.parts if candidates and candidates[0].content else None
    inline = parts[0].inline_data if parts else None
    if inline is None or not inline.data:
        raise ProviderError("Gemini TTS returned no audio data")

    mime_type = inline.mime_type or ""
    rate_match = _RATE_PATTERN.search(mime_type)
    sample_rate = int(rate_match.group(1)) if rate_match else 24000

    return _wrap_pcm_as_wav(inline.data, sample_rate=sample_rate)
