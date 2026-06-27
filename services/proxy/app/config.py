from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    env: str = "development"
    log_level: str = "INFO"

    primary_llm_url: str = "http://localhost:8001"
    candidate_llm_url: str = "http://localhost:8002"
    judge_url: str = "http://localhost:8003"

    mongodb_url: str = "mongodb://localhost:27017/shadowproxy"
    mongodb_db_name: str = "shadowproxy"

    redis_url: str = "redis://localhost:6379"

    primary_timeout: float = 10.0
    candidate_timeout: float = 30.0
    judge_timeout: float = 10.0

    rate_limit_per_minute: int = 60


settings = Settings()
