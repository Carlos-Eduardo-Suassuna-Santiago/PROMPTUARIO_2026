from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Integer, JSON, String, Text
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
            "CONSULTATIONS", "PATIENTS", "DOCTORS", "PRESCRIPTIONS",
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
        Enum("JSON", "CSV", "PDF", name="output_format"),
        default="JSON", nullable=False,
    )
    result_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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
