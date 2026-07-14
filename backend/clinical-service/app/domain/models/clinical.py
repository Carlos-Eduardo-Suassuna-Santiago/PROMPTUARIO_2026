from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean, Date, DateTime, Enum, ForeignKey,
    Integer, String, Text, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.database import Base


def _now():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


# ─── Patient Projection (local read-model from Patient Service events) ────────

class PatientProjection(Base):
    """
    Local denormalized projection of Patient data.
    Updated via RabbitMQ events from Patient Service.
    Never written by Clinical Service directly.
    """
    __tablename__ = "patient_projections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    blood_type: Mapped[str | None] = mapped_column(String(5), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


# ─── Schedule & Slots ─────────────────────────────────────────────────────────

class DoctorSchedule(Base):
    __tablename__ = "doctor_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    doctor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    specialty: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    slots: Mapped[list["TimeSlot"]] = relationship(
        "TimeSlot", back_populates="schedule", cascade="all, delete-orphan"
    )


class TimeSlot(Base):
    __tablename__ = "time_slots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    schedule_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("doctor_schedules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slot_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)  # "HH:MM"
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    schedule: Mapped[DoctorSchedule] = relationship("DoctorSchedule", back_populates="slots")


# ─── Appointments ─────────────────────────────────────────────────────────────

class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doctor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    slot_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("time_slots.id"), nullable=True
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    appointment_type: Mapped[str] = mapped_column(
        Enum("CONSULTATION", "RETURN", "EXAM", "URGENT", name="appointment_type"),
        nullable=False, default="CONSULTATION",
    )
    specialty: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("SCHEDULED", "CONFIRMED", "COMPLETED", "CANCELLED", "NO_SHOW", name="appointment_status"),
        nullable=False, default="SCHEDULED",
    )
    cancellation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cancelled_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    medical_record: Mapped["MedicalRecord | None"] = relationship(
        "MedicalRecord", back_populates="appointment", uselist=False
    )


# ─── Medical Records ──────────────────────────────────────────────────────────

class MedicalRecord(Base):
    __tablename__ = "medical_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    appointment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("appointments.id"), unique=True, nullable=False, index=True
    )
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doctor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    chief_complaint: Mapped[str] = mapped_column(Text, nullable=False)
    anamnesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    physical_exam: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnosis_codes: Mapped[list] = mapped_column(JSON, default=list)
    treatment_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    observations: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Rich structured notes — sanitized JSON with sections
    rich_notes: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Digital signature for integrity verification
    signature_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    ai_analysis_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    appointment: Mapped[Appointment] = relationship("Appointment", back_populates="medical_record")
    prescriptions: Mapped[list["Prescription"]] = relationship(
        "Prescription", back_populates="record", cascade="all, delete-orphan"
    )
    exam_requests: Mapped[list["ExamRequest"]] = relationship(
        "ExamRequest", back_populates="record", cascade="all, delete-orphan"
    )
    certificates: Mapped[list["MedicalCertificate"]] = relationship(
        "MedicalCertificate", back_populates="record", cascade="all, delete-orphan"
    )
    history: Mapped[list["MedicalRecordHistory"]] = relationship(
        "MedicalRecordHistory", back_populates="record", cascade="all, delete-orphan"
    )


class MedicalRecordHistory(Base):
    """Immutable audit trail of every change to a MedicalRecord."""
    __tablename__ = "medical_record_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    record_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("medical_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    changed_by: Mapped[str] = mapped_column(String(36), nullable=False)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    record: Mapped[MedicalRecord] = relationship("MedicalRecord", back_populates="history")


# ─── Prescriptions ────────────────────────────────────────────────────────────

class Prescription(Base):
    __tablename__ = "prescriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    record_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("medical_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    doctor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    medications: Mapped[list] = mapped_column(JSON, default=list)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    valid_days: Mapped[int] = mapped_column(Integer, default=30)

    # PDF generation
    pdf_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pdf_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Digital signature
    signature_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    record: Mapped[MedicalRecord] = relationship("MedicalRecord", back_populates="prescriptions")


class PrescriptionHistory(Base):
    """Immutable audit trail for prescription changes."""
    __tablename__ = "prescription_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    prescription_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    record_id: Mapped[str] = mapped_column(String(36), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(36), nullable=False)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# ─── Exam Requests ────────────────────────────────────────────────────────────

class ExamRequest(Base):
    __tablename__ = "exam_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    record_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("medical_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    doctor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    exam_type: Mapped[str] = mapped_column(String(255), nullable=False)
    urgency: Mapped[str] = mapped_column(
        Enum("ROUTINE", "URGENT", "EMERGENCY", name="exam_urgency"),
        default="ROUTINE", nullable=False,
    )
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Audit trail
    history: Mapped[list["ExamRequestHistory"]] = relationship(
        "ExamRequestHistory", back_populates="exam", cascade="all, delete-orphan"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    record: Mapped[MedicalRecord] = relationship("MedicalRecord", back_populates="exam_requests")


class ExamRequestHistory(Base):
    """Immutable audit trail for exam request changes."""
    __tablename__ = "exam_request_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    exam_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("exam_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    record_id: Mapped[str] = mapped_column(String(36), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(36), nullable=False)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    exam: Mapped[ExamRequest] = relationship("ExamRequest", back_populates="history")


# ─── Medical Certificates ────────────────────────────────────────────────────

class MedicalCertificate(Base):
    __tablename__ = "medical_certificates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    record_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("medical_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    doctor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    days_off: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    pdf_s3_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pdf_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    signature_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    record: Mapped[MedicalRecord] = relationship("MedicalRecord", back_populates="certificates")


class MedicalCertificateHistory(Base):
    """Immutable audit trail for medical certificate changes."""
    __tablename__ = "medical_certificate_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    certificate_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("medical_certificates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    record_id: Mapped[str] = mapped_column(String(36), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(36), nullable=False)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)