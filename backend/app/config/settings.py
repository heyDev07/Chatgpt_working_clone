from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database / cache
    database_url: str = "postgresql+asyncpg://ai_assistant:ai_assistant@localhost:5432/ai_assistant"
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # LLM providers
    openai_api_key: str = ""
    openai_base_url: str = ""  # override to point at an OpenAI-compatible endpoint (e.g. OpenRouter)
    gemini_api_key: str = ""
    default_llm_provider: str = "openai"
    default_openai_model: str = "gpt-4o-mini"
    default_gemini_model: str = "gemini-2.0-flash"

    # RAG: vector store + object storage
    qdrant_url: str = "http://localhost:6333"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "ai_assistant"
    s3_secret_key: str = "ai_assistant_minio"
    s3_bucket: str = "documents"
    # Defaults to gemini: the "openai" provider slot is routed through OpenRouter for free-tier
    # chat testing, and OpenRouter does not expose an embeddings endpoint.
    embedding_provider: str = "gemini"
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768

    # CORS
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
