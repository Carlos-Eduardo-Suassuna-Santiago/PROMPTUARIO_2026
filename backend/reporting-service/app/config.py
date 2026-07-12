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
    S3_PUBLIC_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "promptuario"
    S3_SECRET_KEY: str = "promptuario_pass"
    S3_BUCKET_REPORTS: str = "reports"

    IAM_DB_URL: str = "postgresql://iam:iam_pass@db-iam:5432/iam_db"
    PATIENT_DB_URL: str = "postgresql://patient:patient_pass@db-patient:5432/patient_db"
    CLINICAL_DB_URL: str = "postgresql://clinical:clinical_pass@db-clinical:5432/clinical_db"

    # --- New: Webhook & Scheduling ---
    WEBHOOK_SIGNING_SECRET: str = "reporting-webhook-secret-change-me"
    CELERY_BEAT_SCHEDULE_FILENAME: str = "/tmp/celerybeat-schedule"
    CUSTOM_SQL_TEMPLATES: dict = {
        "consultations_by_doctor": """
            SELECT doctor_id, stat_date, value AS consultations
            FROM daily_stats
            WHERE stat_type = 'DOCTOR_CONSULTATIONS'
              AND stat_date BETWEEN :from_date AND :to_date
            ORDER BY stat_date DESC, doctor_id
        """,
        "patient_growth": """
            SELECT stat_date, value AS new_patients
            FROM daily_stats
            WHERE stat_type = 'NEW_PATIENTS'
              AND stat_date BETWEEN :from_date AND :to_date
            ORDER BY stat_date DESC
        """,
        "cancellation_rate": """
            SELECT
                c.stat_date,
                c.value AS consultations,
                x.value AS cancellations,
                ROUND(100.0 * x.value / NULLIF(c.value, 0), 2) AS cancel_pct
            FROM daily_stats c
            LEFT JOIN daily_stats x
                ON x.stat_date = c.stat_date AND x.stat_type = 'CANCELLATIONS'
            WHERE c.stat_type = 'CONSULTATIONS'
              AND c.stat_date BETWEEN :from_date AND :to_date
            ORDER BY c.stat_date DESC
        """,
    }


settings = Settings()
