from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "INFO"

    # LLM
    dashscope_api_key: str = ""
    llm_model: str = "qwen-turbo"
    request_timeout: float = 30.0

    # Database
    database_url: str = "sqlite:///./canal_mind.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
