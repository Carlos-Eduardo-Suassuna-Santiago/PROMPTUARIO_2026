"""AI Service configuration."""
from __future__ import annotations

import logging
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SERVICE_NAME: str = "ai-service"
    LOG_LEVEL: str = "INFO"

    MONGODB_URL: str = "mongodb://ai:ai_pass@localhost:27017/ai_db?authSource=admin"
    RABBITMQ_URL: str = "amqp://promptuario:promptuario_pass@localhost:5672/"
    REDIS_URL: str = "redis://localhost:6379/2"

    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"

    # LLM configuration
    LLM_API_KEY: str = ""
    LLM_API_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_MAX_TOKENS: int = 1000
    LLM_TEMPERATURE: float = 0.1
    LLM_TIMEOUT_SECONDS: int = 60
    LLM_JSON_MODE: bool = True  # Some providers like Groq may not support response_format

    # Retry configuration
    LLM_RETRY_MAX_ATTEMPTS: int = 3
    LLM_RETRY_MIN_WAIT: int = 2
    LLM_RETRY_MAX_WAIT: int = 30

    # Circuit breaker
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int = 60

    # Cache
    CACHE_ENABLED: bool = True
    LLM_CACHE_TTL_SECONDS: int = 3600  # 1h

    # Analysis
    ANALYSIS_TIMEOUT_SECONDS: int = 120  # total timeout including retries


settings = Settings()

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)