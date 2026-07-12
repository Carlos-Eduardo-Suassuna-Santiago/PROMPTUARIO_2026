from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


# ─── Allergy ─────────────────────────────────────────────────────────────────

class AllergyCreate(BaseModel):
    substance: str = Field(min_length=2, max_length=255)
    severity: Literal["MILD", "MODERATE", "SEVERE"]
    reaction_type: str | None = None
    notes: str | None = None


class AllergyResponse(BaseModel):
    id: str
    patient_id: str
    substance: str
    severity: str
    reaction_type: str | None
    notes: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── Vaccine ─────────────────────────────────────────────────────────────────

class VaccineCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    dose: str | None = None
    applied_at: date | None = None
    next_dose_at: date | None = None
    notes: str | None = None


class VaccineResponse(BaseModel):
    id: str
    patient_id: str
    name: str
    dose: str | None
    applied_at: date | None
    next_dose_at: date | None
    notes: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── ContinuousMedication ────────────────────────────────────────────────────

class MedicationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    dosage: str = Field(min_length=1, max_length=100)
    frequency: str = Field(min_length=1, max_length=100)
    prescribing_doctor: str | None = None
    started_at: date | None = None
    notes: str | None = None


class MedicationUpdate(BaseModel):
    dosage: str | None = Field(None, min_length=1, max_length=100)
    frequency: str | None = Field(None, min_length=1, max_length=100)
    prescribing_doctor: str | None = None
    notes: str | None = None


class MedicationDeactivate(BaseModel):
    ended_at: date | None = None
    end_reason: str | None = Field(None, max_length=255)


class MedicationResponse(BaseModel):
    id: str
    patient_id: str
    name: str
    dosage: str
    frequency: str
    prescribing_doctor: str | None
    started_at: date | None
    ended_at: date | None
    end_reason: str | None
    active: bool
    version: int
    notes: str | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class MedicationHistoryResponse(BaseModel):
    id: str
    patient_id: str
    medication_id: str | None
    name: str
    dosage: str
    frequency: str
    prescribing_doctor: str | None
    started_at: date | None
    ended_at: date | None
    end_reason: str | None
    active: bool
    version: int
    change_type: str
    changed_by: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── Patient Document ────────────────────────────────────────────────────────

class DocumentUploadResponse(BaseModel):
    id: str
    patient_id: str
    document_type: str
    file_name: str
    s3_key: str
    file_size: int
    mime_type: str
    file_hash: str | None
    description: str | None
    uploaded_by: str | None
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: str
    patient_id: str
    document_type: str
    file_name: str
    file_size: int
    mime_type: str
    file_hash: str | None
    description: str | None
    uploaded_by: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    size: int


class DocumentDownloadResponse(BaseModel):
    download_url: str
    expires_in_seconds: int = 300


# ─── Patient ─────────────────────────────────────────────────────────────────

class AddressSchema(BaseModel):
    street: str | None = None
    city: str | None = None
    state: str | None = Field(None, max_length=2)
    zip_code: str | None = None


class EmergencyContactSchema(BaseModel):
    name: str | None = None
    phone: str | None = None
    relation: str | None = None


class PatientCreate(BaseModel):
    user_id: str
    full_name: str = Field(min_length=2, max_length=255)
    cpf: str | None = Field(None, pattern=r"^\d{3}\.\d{3}\.\d{3}-\d{2}$")
    date_of_birth: date | None = None
    gender: Literal["M", "F", "OTHER"] | None = None
    blood_type: str | None = Field(None, max_length=5)
    phone: str | None = None
    email: EmailStr | None = None
    address: AddressSchema | None = None
    emergency_contact: EmergencyContactSchema | None = None
    notes: str | None = None


class PatientUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=255)
    cpf: str | None = Field(None, pattern=r"^\d{3}\.\d{3}\.\d{3}-\d{2}$")
    date_of_birth: date | None = None
    gender: Literal["M", "F", "OTHER"] | None = None
    blood_type: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    address: AddressSchema | None = None
    emergency_contact: EmergencyContactSchema | None = None
    notes: str | None = None


class PatientResponse(BaseModel):
    id: str
    user_id: str
    full_name: str
    cpf: str | None
    date_of_birth: date | None
    gender: str | None
    blood_type: str | None
    phone: str | None
    email: str | None
    street: str | None
    city: str | None
    state: str | None
    zip_code: str | None
    emergency_name: str | None
    emergency_phone: str | None
    emergency_relation: str | None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class PatientSummaryResponse(BaseModel):
    """Lightweight read-model used by Clinical Service."""
    id: str
    user_id: str
    full_name: str
    date_of_birth: date | None
    blood_type: str | None
    phone: str | None
    allergies: list[AllergyResponse]
    medications: list[MedicationResponse]
    model_config = {"from_attributes": True}


class PatientListResponse(BaseModel):
    items: list[PatientResponse]
    total: int
    page: int
    size: int