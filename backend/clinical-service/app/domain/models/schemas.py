from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ─── Schedule / Slots ────────────────────────────────────────────────────────

class TimeSlotCreate(BaseModel):
    slot_date: date
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")


class TimeSlotResponse(BaseModel):
    id: str
    schedule_id: str
    slot_date: date
    start_time: str
    end_time: str
    is_available: bool
    model_config = {"from_attributes": True}


class ScheduleCreate(BaseModel):
    specialty: str | None = None
    slots: list[TimeSlotCreate] = []


class ScheduleResponse(BaseModel):
    id: str
    doctor_id: str
    specialty: str | None
    is_active: bool
    slots: list[TimeSlotResponse] = []
    model_config = {"from_attributes": True}


# ─── Appointments ────────────────────────────────────────────────────────────

class AppointmentCreate(BaseModel):
    patient_id: str | None = None  # Auto-atribuído quando perfil for PATIENT
    doctor_id: str
    slot_id: str | None = None
    scheduled_at: datetime
    appointment_type: Literal["CONSULTATION", "RETURN", "EXAM", "URGENT"] = "CONSULTATION"
    specialty: str | None = None
    notes: str | None = None


class AppointmentCancelRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=255)


class AppointmentResponse(BaseModel):
    id: str
    patient_id: str
    doctor_id: str
    scheduled_at: datetime
    appointment_type: str
    specialty: str | None
    status: str
    cancellation_reason: str | None
    notes: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class AppointmentListResponse(BaseModel):
    items: list[AppointmentResponse]
    total: int
    page: int
    size: int


# ─── Medical Records ─────────────────────────────────────────────────────────

class MedicalRecordCreate(BaseModel):
    appointment_id: str
    chief_complaint: str = Field(min_length=5)
    anamnesis: str | None = None
    physical_exam: str | None = None
    diagnosis: str | None = None
    diagnosis_codes: list[str] = []
    treatment_plan: str | None = None
    observations: str | None = None


class MedicalRecordUpdate(BaseModel):
    chief_complaint: str | None = None
    anamnesis: str | None = None
    physical_exam: str | None = None
    diagnosis: str | None = None
    diagnosis_codes: list[str] | None = None
    treatment_plan: str | None = None
    observations: str | None = None


class MedicalRecordHistoryResponse(BaseModel):
    id: str
    changed_by: str
    change_type: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── Prescriptions ───────────────────────────────────────────────────────────

class MedicationItem(BaseModel):
    name: str
    dosage: str
    frequency: str
    duration_days: int = 7
    instructions: str | None = None


class PrescriptionCreate(BaseModel):
    medications: list[MedicationItem] = Field(min_length=1)
    instructions: str | None = None
    valid_days: int = Field(30, ge=1, le=365)


class PrescriptionResponse(BaseModel):
    id: str
    record_id: str
    patient_id: str
    doctor_id: str
    medications: list[dict[str, Any]]
    instructions: str | None
    valid_days: int
    pdf_s3_key: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── Exam Requests ───────────────────────────────────────────────────────────

class ExamRequestCreate(BaseModel):
    exam_type: str = Field(min_length=3, max_length=255)
    urgency: Literal["ROUTINE", "URGENT", "EMERGENCY"] = "ROUTINE"
    instructions: str | None = None


class ExamResultUpdate(BaseModel):
    result: str = Field(min_length=5)
    result_date: datetime | None = None


class ExamRequestResponse(BaseModel):
    id: str
    record_id: str
    patient_id: str
    exam_type: str
    urgency: str
    instructions: str | None
    result: str | None
    result_date: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}


class MedicalRecordResponse(BaseModel):
    id: str
    appointment_id: str
    patient_id: str
    doctor_id: str
    chief_complaint: str
    anamnesis: str | None
    physical_exam: str | None
    diagnosis: str | None
    diagnosis_codes: list[str]
    treatment_plan: str | None
    observations: str | None
    ai_analysis_id: str | None
    prescriptions: list[PrescriptionResponse] = []
    exam_requests: list[ExamRequestResponse] = []
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
