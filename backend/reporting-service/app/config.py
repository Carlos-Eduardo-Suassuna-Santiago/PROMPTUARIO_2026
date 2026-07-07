from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SERVICE_NAME: str = "reporting-service"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "postgresql+asyncpg://reporting:reporting_pass@localhost:5432/reporting_db"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    RABBITMQ_URL: str = "amqp://promptuario:promptuario_pass@localhost:5672/"

    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"

    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "promptuario"
    S3_SECRET_KEY: str = "promptuario_pass"
    S3_BUCKET_REPORTS: str = "reports"

    IAM_DB_URL: str = "postgresql://iam:iam_pass@db-iam:5432/iam_db"
    PATIENT_DB_URL: str = "postgresql://patient:patient_pass@db-patient:5432/patient_db"
    CLINICAL_DB_URL: str = "postgresql://clinical:clinical_pass@db-clinical:5432/clinical_db"


settings = Settings()
