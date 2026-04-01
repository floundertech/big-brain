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
    # Label-based routing (JSON string of label configs)
    gmail_label_customer: str = "big-brain/customer"
    gmail_label_research: str = "big-brain/research"
    gmail_label_reference: str = "big-brain/reference"
    gmail_remove_label_after_processing: bool = False
    # RSS / Miniflux
    miniflux_url: str | None = None
    miniflux_api_key: str | None = None
    rss_poll_interval_seconds: int = 3600
    rss_digest_hour: int = 5
    rss_digest_model: str = "claude-haiku-4-5-20251001"
    rss_relevance_topics: str = ""
    rss_initial_backfill_days: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
