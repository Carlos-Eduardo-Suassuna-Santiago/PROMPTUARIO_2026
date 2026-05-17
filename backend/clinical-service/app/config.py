from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SERVICE_NAME: str = "clinical-service"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql+asyncpg://clinical:clinical_pass@localhost:5432/clinical_db"
    RABBITMQ_URL: str = "amqp://promptuario:promptuario_pass@localhost:5672/"

    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"

    # S3 / MinIO
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "promptuario"
    S3_SECRET_KEY: str = "promptuario_pass"
    S3_BUCKET_PRESCRIPTIONS: str = "prescriptions"

    # Business rules
    APPOINTMENT_CANCEL_HOURS_MIN: int = 24


settings = Settings()
