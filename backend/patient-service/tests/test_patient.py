"""Patient Service unit tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.models.schemas import AllergyCreate, PatientCreate


def test_patient_schema_valid():
    p = PatientCreate(
        user_id="usr_abc",
        full_name="João Silva",
        date_of_birth="1990-01-15",
        blood_type="O+",
        phone="+55 84 99999-0000",
    )
    assert p.full_name == "João Silva"
    assert p.blood_type == "O+"


def test_patient_schema_invalid_cpf():
    with pytest.raises(ValidationError):
        PatientCreate(
            user_id="usr_abc",
            full_name="João Silva",
            cpf="12345678900",  # missing dots and dash
        )


def test_allergy_severity_validation():
    with pytest.raises(ValidationError):
        AllergyCreate(substance="Penicillin", severity="UNKNOWN")

    a = AllergyCreate(substance="Penicillin", severity="SEVERE", reaction_type="Anaphylaxis")
    assert a.severity == "SEVERE"


def test_allergy_substance_min_length():
    with pytest.raises(ValidationError):
        AllergyCreate(substance="A", severity="MILD")


def test_vaccine_schema():
    from app.domain.models.schemas import VaccineCreate
    from datetime import date
    v = VaccineCreate(
        name="Hepatite B",
        dose="1ª dose",
        applied_at=date(2023, 6, 1),
    )
    assert v.name == "Hepatite B"


def test_medication_schema():
    from app.domain.models.schemas import MedicationCreate
    m = MedicationCreate(
        name="Losartana",
        dosage="50mg",
        frequency="1x ao dia",
        prescribing_doctor="Dr. Carlos",
    )
    assert m.name == "Losartana"
    assert m.dosage == "50mg"
