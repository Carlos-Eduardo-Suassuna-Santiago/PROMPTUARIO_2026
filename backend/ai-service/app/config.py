"""AI Service — complete single-file implementation for clarity."""
# ─── config.py ───────────────────────────────────────────────────────────────
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SERVICE_NAME: str = "ai-service"
    LOG_LEVEL: str = "INFO"

    MONGODB_URL: str = "mongodb://ai:ai_pass@localhost:27017/ai_db?authSource=admin"
    RABBITMQ_URL: str = "amqp://promptuario:promptuario_pass@localhost:5672/"
    REDIS_URL: str = "redis://localhost:6379/2"

    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"

    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_MAX_TOKENS: int = 1000


settings = Settings()
