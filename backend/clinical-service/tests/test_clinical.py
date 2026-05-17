"""Clinical Service unit tests — business rule coverage."""
from __future__ import annotations

import pytest
from pydantic import ValidationError
from datetime import datetime, timezone, timedelta

from app.domain.models.schemas import (
    AppointmentCreate,
    AppointmentCancelRequest,
    MedicalRecordCreate,
    PrescriptionCreate,
    MedicationItem,
    ExamRequestCreate,
    TimeSlotCreate,
)


def test_appointment_create_valid():
    future = datetime.now(timezone.utc) + timedelta(days=3)
    a = AppointmentCreate(
        patient_id="pat_001",
        doctor_id="doc_001",
        scheduled_at=future,
        appointment_type="CONSULTATION",
        specialty="Clínica Geral",
    )
    assert a.appointment_type == "CONSULTATION"


def test_appointment_type_validation():
    future = datetime.now(timezone.utc) + timedelta(days=3)
    with pytest.raises(ValidationError):
        AppointmentCreate(
            patient_id="pat_001",
            doctor_id="doc_001",
            scheduled_at=future,
            appointment_type="INVALID_TYPE",
        )


def test_cancel_reason_min_length():
    with pytest.raises(ValidationError):
        AppointmentCancelRequest(reason="No")  # too short


def test_medical_record_create_valid():
    m = MedicalRecordCreate(
        appointment_id="appt_001",
        chief_complaint="Dor de cabeça persistente há 3 dias",
        anamnesis="Sem histórico relevante",
        diagnosis_codes=["G44.309"],
    )
    assert m.appointment_id == "appt_001"
    assert len(m.diagnosis_codes) == 1


def test_prescription_create_requires_medications():
    with pytest.raises(ValidationError):
        PrescriptionCreate(medications=[])  # empty list not allowed


def test_prescription_valid():
    rx = PrescriptionCreate(
        medications=[
            MedicationItem(name="Dipirona", dosage="500mg", frequency="6/6h", duration_days=5)
        ],
        instructions="Tomar com água",
        valid_days=30,
    )
    assert len(rx.medications) == 1
    assert rx.medications[0].name == "Dipirona"


def test_exam_urgency_validation():
    with pytest.raises(ValidationError):
        ExamRequestCreate(exam_type="Hemograma", urgency="SUPER_URGENT")

    e = ExamRequestCreate(exam_type="Hemograma Completo", urgency="URGENT")
    assert e.urgency == "URGENT"


def test_time_slot_format():
    with pytest.raises(ValidationError):
        TimeSlotCreate(
            slot_date="2026-06-01",
            start_time="9:00",    # missing leading zero
            end_time="10:00",
        )

    from datetime import date
    slot = TimeSlotCreate(
        slot_date=date(2026, 6, 1),
        start_time="09:00",
        end_time="10:00",
    )
    assert slot.start_time == "09:00"


def test_exam_type_min_length():
    with pytest.raises(ValidationError):
        ExamRequestCreate(exam_type="AB", urgency="ROUTINE")  # < 3 chars
