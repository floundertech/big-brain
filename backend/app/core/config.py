from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    anthropic_api_key: str
    embed_model: str = "nomic-ai/nomic-embed-text-v1.5"
    embed_dim: int = 768
    tavily_api_key: str | None = None
    dt_otlp_endpoint: str | None = None  # e.g. https://{env}.live.dynatrace.com/api/v2/otlp
    dt_api_token: str | None = None      # needs openTelemetryTrace.ingest scope
    gmail_poll_interval_seconds: int = 300
    gmail_ingest_label: str = "big-brain"
    gmail_done_label: str = "big-brain/done"

    class Config:
        env_file = ".env"


settings = Settings()
