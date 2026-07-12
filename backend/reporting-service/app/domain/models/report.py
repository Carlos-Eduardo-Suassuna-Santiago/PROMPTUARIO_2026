from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.database import Base


def _now():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


class ReportJob(Base):
    __tablename__ = "report_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    report_type: Mapped[str] = mapped_column(
        Enum(
            "CONSULTATIONS", "PATIENTS", "DOCTORS", "PRESCRIPTIONS", "CUSTOM", "FULL_SYSTEM",
            name="report_type"
        ),
        nullable=False,
    )
    requested_by: Mapped[str] = mapped_column(String(36), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(
        Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", name="report_status"),
        default="PENDING", nullable=False,
    )
    output_format: Mapped[str] = mapped_column(
        Enum("JSON", "CSV", "PDF", "XLSX", name="output_format"),
        default="JSON", nullable=False,
    )
    result_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    schedule_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    webhook_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReportSchedule(Base):
    """Recurring report schedule driven by Celery Beat."""
    __tablename__ = "report_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    report_type: Mapped[str] = mapped_column(String(30), nullable=False)
    output_format: Mapped[str] = mapped_column(String(10), default="XLSX")
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    recipients: Mapped[dict] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=_now, nullable=True)


class WebhookConfig(Base):
    """Registered webhook endpoint for job completion notifications."""
    __tablename__ = "webhook_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    secret: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    retry_interval_seconds: Mapped[int] = mapped_column(Integer, default=60)
    events: Mapped[dict] = mapped_column(JSON, default=list)
    last_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=_now, nullable=True)


class WebhookDeliveryLog(Base):
    """Delivery attempt log for webhook notifications."""
    __tablename__ = "webhook_delivery_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    webhook_config_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ReportAuditLog(Base):
    """Audit trail for report generation, schedule changes, and webhook deliveries."""
    __tablename__ = "report_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_type: Mapped[str] = mapped_column(
        String(40), nullable=False, index=True,
        comment="e.g. REPORT_REQUESTED, REPORT_COMPLETED, SCHEDULE_CREATED, WEBHOOK_SENT",
    )
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    description: Mapped[str] = mapped_column(String(500), default="")
    performed_by: Mapped[str] = mapped_column(String(36), nullable=False)
    event_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class DailyStats(Base):
    """Pre-aggregated daily statistics updated by event consumers."""
    __tablename__ = "daily_stats"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    stat_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    stat_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    value: Mapped[int] = mapped_column(Integer, default=0)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, name="metadata")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)