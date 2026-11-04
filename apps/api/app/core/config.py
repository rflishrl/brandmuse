from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with fail-fast validation on startup."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server & Networking
    PORT: int = Field(default=8000, description="Port the API server listens on")
    ENVIRONMENT: str = Field(default="development", description="Runtime environment")
    CORS_ORIGIN: str = Field(
        default="http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
        description="Comma-separated allowed CORS origins",
    )

    # Database & Storage
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgrespassword@localhost:5432/brandmuse",
        description="Async connection string for FastAPI application",
    )
    MIGRATION_DATABASE_URL: str | None = Field(
        default=None,
        description="Connection string for running Alembic migrations",
    )
    DB_POOLER_MODE: bool = Field(
        default=False,
        description="Set True when connecting via Supabase transaction pooler (port 6543)",
    )
    FTS_CONFIG: str = Field(
        default="english",
        description="Postgres tsvector text search dictionary config",
    )

    # AI Providers & Dimensions
    LLM_PROVIDER: str = Field(default="openai", description="Active LLM provider: openai | ollama")
    EMBEDDING_PROVIDER: str = Field(
        default="openai", description="Active embedding provider: openai | ollama"
    )
    EMBEDDING_DIM: int = Field(
        default=1536,
        description="Vector dimension for embeddings (1536 for OpenAI text-embedding-3-small)",
    )
    IMAGE_PROVIDER: str = Field(
        default="stability", description="Active image generation provider: stability | replicate"
    )

    # Credentials
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434", description="Ollama API base URL"
    )
    STABILITY_API_KEY: str = Field(default="", description="Stability AI API key")
    REPLICATE_API_TOKEN: str = Field(default="", description="Replicate API token")

    # Supabase Storage (for permanent image URLs)
    SUPABASE_URL: str = Field(default="", description="Supabase project URL")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(
        default="", description="Supabase service role key (server-side only)"
    )
    SUPABASE_STORAGE_BUCKET: str = Field(
        default="brandmuse-images", description="Storage bucket name for generated images"
    )

    # Observability (Langfuse)
    LANGFUSE_PUBLIC_KEY: str = Field(default="", description="Langfuse public key")
    LANGFUSE_SECRET_KEY: str = Field(default="", description="Langfuse secret key")
    LANGFUSE_HOST: str = Field(
        default="https://cloud.langfuse.com", description="Langfuse host URL"
    )
    LANGFUSE_PUBLIC_URL: str | None = Field(
        default=None, description="Public Langfuse URL for direct trace links"
    )
    TRACE_USER_CONTENT: bool = Field(
        default=False,
        description="Whether to trace raw content of user uploads in Langfuse",
    )

    # Safety & Abuse Control
    DAILY_LLM_LIMIT: int = Field(default=200, description="Global daily cap on LLM calls")
    DAILY_IMAGE_LIMIT: int = Field(default=25, description="Global daily cap on image generations")
    SESSION_IMAGE_HOURLY_LIMIT: int = Field(
        default=5, description="Max image generations per hour per session"
    )
    RATE_LIMIT_PER_MINUTE: int = Field(
        default=30, description="General rate limit per minute per IP"
    )

    @property
    def cors_origins(self) -> list[str]:
        """Parsed list of allowed CORS origins."""
        return [origin.strip() for origin in self.CORS_ORIGIN.split(",") if origin.strip()]

    @property
    def effective_migration_db_url(self) -> str:
        """Fallback to DATABASE_URL if MIGRATION_DATABASE_URL is not set."""
        return self.MIGRATION_DATABASE_URL or self.DATABASE_URL


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
