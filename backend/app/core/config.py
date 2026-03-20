from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    anthropic_api_key: str
    embed_model: str = "nomic-ai/nomic-embed-text-v1.5"
    embed_dim: int = 768

    class Config:
        env_file = ".env"


settings = Settings()
