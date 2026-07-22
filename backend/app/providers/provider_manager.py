from functools import lru_cache

from app.config.settings import get_settings
from app.core.exceptions import ValidationAppError
from app.providers.base_provider import BaseProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.openai_provider import OpenAIProvider


class ProviderManager:
    def __init__(self):
        settings = get_settings()
        self._default_provider_name = settings.default_llm_provider
        self._providers: dict[str, BaseProvider] = {}

        if settings.openai_api_key:
            self._providers["openai"] = OpenAIProvider(settings.openai_api_key, settings.openai_base_url)
        if settings.gemini_api_key:
            self._providers["gemini"] = GeminiProvider(settings.gemini_api_key)

    def get_provider(self, name: str | None = None) -> BaseProvider:
        provider_name = name or self._default_provider_name
        provider = self._providers.get(provider_name)
        if not provider:
            raise ValidationAppError(f"Provider '{provider_name}' is not configured")
        return provider

    def get_default_provider_name(self) -> str:
        return self._default_provider_name

    def default_model_for(self, provider_name: str) -> str:
        settings = get_settings()
        return {
            "openai": settings.default_openai_model,
            "gemini": settings.default_gemini_model,
        }.get(provider_name, "")


@lru_cache
def get_provider_manager() -> ProviderManager:
    return ProviderManager()
