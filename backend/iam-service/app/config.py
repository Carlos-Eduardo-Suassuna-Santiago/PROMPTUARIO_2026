from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    SERVICE_NAME: str = "iam-service"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://iam:iam_pass@localhost:5432/iam_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # RabbitMQ
    RABBITMQ_URL: str = "amqp://promptuario:promptuario_pass@localhost:5672/"

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # First admin user (created on startup if DB is empty)
    # OAuth Google
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    # URL base do gateway (para construir callback URLs do OAuth)
    OAUTH_REDIRECT_BASE_URL: str = "http://localhost:8000"
    # URL do frontend para receber tokens após OAuth
    FRONTEND_CALLBACK_URL: str = "http://localhost:3000/auth/callback"

    FIRST_ADMIN_EMAIL: str = "admin@promptuario.health"
    FIRST_ADMIN_PASSWORD: str = "Admin@12345"
    FIRST_ADMIN_NAME: str = "Administrador"

    # SMTP Configuration
    SMTP_SERVER: str = "mailpit"
    SMTP_PORT: int = 1025
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@promptuario.health"


settings = Settings()
