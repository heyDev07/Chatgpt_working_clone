from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # "development" (the default) or "production" - drives environment-sensitive behavior like
    # the refresh cookie's Secure flag (auth.py), instead of that being a hardcoded value someone
    # has to remember to flip by hand before a real deployment.
    environment: str = "development"
    # "text" (default, readable in a terminal) or "json" (structured, for a log shipper to
    # parse) - see app/core/logging_config.py.
    log_format: str = "text"

    # Database / cache
    database_url: str = "postgresql+asyncpg://ai_assistant:ai_assistant@localhost:5432/ai_assistant"
    redis_url: str = "redis://localhost:6379/0"
    # SQLAlchemy's own defaults (pool_size=5, max_overflow=10 -> 15 connections) were the actual
    # bottleneck a real load test found (Phase 18) - 20/60s stayed under 30ms p95 with zero
    # errors, but 100/30s showed tail latency climbing into the hundreds of ms with a fast median,
    # the textbook signature of requests queueing for a pool connection rather than the app or DB
    # actually struggling. 30 total per replica leaves headroom under Postgres's default
    # max_connections=100 for multiple ECS replicas (Terraform's backend_desired_count) without
    # needing per-deployment tuning for a single-replica default.
    db_pool_size: int = 20
    db_max_overflow: int = 10

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

    # MCP servers - each is optional; a missing key just means that server's tools don't
    # register at startup, not an error (see app/tools/registry.register_mcp_servers).
    tavily_api_key: str = ""
    tavily_mcp_url: str = "https://mcp.tavily.com/mcp/"

    # SQL database chat (Phase 9g): a dedicated Postgres role, granted SELECT on the sql_demo
    # schema only (see the 0eb2d0957976 migration), is the enforcement boundary the LLM-generated
    # SQL runs under - query-string validation in the tool is a second layer, not the only one.
    sql_demo_db_password: str = "sql_demo_readonly_pw"

    # Google OAuth (Gmail + Calendar) - one client covers both, scopes requested per-flow rather
    # than needing separate apps. Empty defaults mean the connect flow is simply unavailable
    # until configured, same graceful-degradation pattern as tavily_api_key above.
    google_client_id: str = ""
    google_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v1/oauth/google/callback"
    # Separate redirect_uri for "Sign in with Google" (app/services/google_login_service.py) -
    # same OAuth client, but Google requires an exact registered match per redirect_uri, and this
    # flow is a fundamentally different callback (creates/logs in a user, no existing session)
    # from the Gmail/Calendar-connect one above, so it can't reuse that URI.
    google_login_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    # LinkedIn connect (profile identity only - see linkedin_oauth_service.py's docstring for
    # why there's no LinkedIn tools file the way google_workspace.py exists for Google).
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_oauth_redirect_uri: str = "http://localhost:8000/api/v1/oauth/linkedin/callback"

    # CORS
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
