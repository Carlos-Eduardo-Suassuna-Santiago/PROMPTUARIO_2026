from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.patient import Allergy, ContinuousMedication, Patient, Vaccine
from app.domain.models.schemas import (
    AllergyCreate,
    MedicationCreate,
    PatientCreate,
    PatientUpdate,
    VaccineCreate,
)
from app.infrastructure.repositories.patient_repository import (
    AllergyRepository,
    MedicationRepository,
    PatientRepository,
    VaccineRepository,
)
from shared.events import AllergyAddedEvent, PatientCreatedEvent, PatientUpdatedEvent
from shared.events.broker import EventPublisher


class PatientService:
    def __init__(self, session: AsyncSession, publisher: EventPublisher):
        self.repo = PatientRepository(session)
        self.publisher = publisher

    async def create(self, data: PatientCreate) -> Patient:
        if data.cpf and await self.repo.exists_cpf(data.cpf):
            raise HTTPException(status_code=409, detail="CPF já cadastrado")

        patient = Patient(
            id=str(uuid.uuid4()),
            user_id=data.user_id,
            full_name=data.full_name,
            cpf=data.cpf,
            date_of_birth=data.date_of_birth,
            gender=data.gender,
            blood_type=data.blood_type,
            phone=data.phone,
            email=str(data.email) if data.email else None,
        )
        if data.address:
            patient.street = data.address.street
            patient.city = data.address.city
            patient.state = data.address.state
            patient.zip_code = data.address.zip_code
        if data.emergency_contact:
            patient.emergency_name = data.emergency_contact.name
            patient.emergency_phone = data.emergency_contact.phone
            patient.emergency_relation = data.emergency_contact.relation

        patient = await self.repo.create(patient)
        await self.publisher.publish(
            PatientCreatedEvent(
                patient_id=patient.id,
                user_id=patient.user_id,
                date_of_birth=str(patient.date_of_birth) if patient.date_of_birth else None,
                blood_type=patient.blood_type,
            )
        )
        return patient

    async def get(self, patient_id: str) -> Patient:
        p = await self.repo.get_by_id(patient_id)
        if not p:
            raise HTTPException(status_code=404, detail="Paciente não encontrado")
        return p

    async def get_by_user(self, user_id: str) -> Patient:
        p = await self.repo.get_by_user_id(user_id)
        if not p:
            raise HTTPException(status_code=404, detail="Paciente não encontrado")
        return p

    async def get_summary(self, patient_id: str) -> Patient:
        p = await self.repo.get_by_id(patient_id, load_relations=True)
        if not p:
            raise HTTPException(status_code=404, detail="Paciente não encontrado")
        return p

    async def list_patients(self, page: int, size: int, search: str | None):
        return await self.repo.list_patients(page, size, search)

    async def update(self, patient_id: str, data: PatientUpdate, current_user_id: str, current_role: str) -> Patient:
        patient = await self.get(patient_id)
        # Patients can only edit their own record unless ADMIN/DOCTOR/ATTENDANT
        if current_role == "PATIENT" and patient.user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Acesso negado")

        changed = []
        fields = {
            "full_name": data.full_name,
            "date_of_birth": data.date_of_birth,
            "gender": data.gender,
            "blood_type": data.blood_type,
            "phone": data.phone,
            "notes": data.notes,
        }
        for field, value in fields.items():
            if value is not None and getattr(patient, field) != value:
                setattr(patient, field, value)
                changed.append(field)

        if data.email is not None:
            patient.email = str(data.email)
            changed.append("email")
        if data.address:
            for attr in ("street", "city", "state", "zip_code"):
                val = getattr(data.address, attr)
                if val is not None:
                    setattr(patient, attr, val)
                    changed.append(attr)
        if data.emergency_contact:
            for attr in ("name", "phone", "relation"):
                val = getattr(data.emergency_contact, attr)
                dest = f"emergency_{attr}"
                if val is not None:
                    setattr(patient, dest, val)
                    changed.append(dest)

        patient = await self.repo.update(patient)
        if changed:
            await self.publisher.publish(
                PatientUpdatedEvent(
                    patient_id=patient.id,
                    changed_fields=changed,
                    phone=patient.phone,
                )
            )
        return patient

    async def deactivate(self, patient_id: str) -> None:
        patient = await self.get(patient_id)
        patient.is_active = False
        await self.repo.update(patient)

    async def anonymize(self, patient_id: str) -> None:
        """LGPD right-to-erasure: replace PII with hashed tokens."""
        import hashlib
        patient = await self.get(patient_id)
        patient.full_name = f"ANONYMIZED_{hashlib.sha256(patient.id.encode()).hexdigest()[:8]}"
        patient.cpf = None
        patient.phone = None
        patient.email = None
        patient.street = None
        patient.city = None
        patient.zip_code = None
        patient.emergency_name = None
        patient.emergency_phone = None
        patient.notes = None
        patient.anonymized = True
        patient.is_active = False
        await self.repo.update(patient)


class AllergyService:
    def __init__(self, session: AsyncSession, publisher: EventPublisher):
        self.repo = AllergyRepository(session)
        self.patient_repo = PatientRepository(session)
        self.publisher = publisher

    async def _check_patient(self, patient_id: str) -> None:
        if not await self.patient_repo.get_by_id(patient_id):
            raise HTTPException(status_code=404, detail="Paciente não encontrado")

    async def list(self, patient_id: str) -> list[Allergy]:
        await self._check_patient(patient_id)
        return await self.repo.list_by_patient(patient_id)

    async def create(self, patient_id: str, data: AllergyCreate) -> Allergy:
        await self._check_patient(patient_id)
        allergy = Allergy(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            substance=data.substance,
            severity=data.severity,
            reaction_type=data.reaction_type,
            notes=data.notes,
        )
        allergy = await self.repo.create(allergy)
        await self.publisher.publish(
            AllergyAddedEvent(
                patient_id=patient_id,
                allergy_id=allergy.id,
                substance=allergy.substance,
                severity=allergy.severity,
            )
        )
        return allergy

    async def delete(self, patient_id: str, allergy_id: str) -> None:
        allergy = await self.repo.get(allergy_id, patient_id)
        if not allergy:
            raise HTTPException(status_code=404, detail="Alergia não encontrada")
        await self.repo.delete(allergy)


class VaccineService:
    def __init__(self, session: AsyncSession, publisher: EventPublisher):
        self.repo = VaccineRepository(session)
        self.patient_repo = PatientRepository(session)

    async def list(self, patient_id: str) -> list[Vaccine]:
        return await self.repo.list_by_patient(patient_id)

    async def create(self, patient_id: str, data: VaccineCreate) -> Vaccine:
        if not await self.patient_repo.get_by_id(patient_id):
            raise HTTPException(status_code=404, detail="Paciente não encontrado")
        vaccine = Vaccine(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            name=data.name,
            dose=data.dose,
            applied_at=data.applied_at,
            next_dose_at=data.next_dose_at,
            notes=data.notes,
        )
        return await self.repo.create(vaccine)

    async def delete(self, patient_id: str, vaccine_id: str) -> None:
        vaccine = await self.repo.get(vaccine_id, patient_id)
        if not vaccine:
            raise HTTPException(status_code=404, detail="Vacina não encontrada")
        await self.repo.delete(vaccine)


class MedicationService:
    def __init__(self, session: AsyncSession, publisher: EventPublisher):
        self.repo = MedicationRepository(session)
        self.patient_repo = PatientRepository(session)

    async def list(self, patient_id: str, active_only: bool = False) -> list[ContinuousMedication]:
        return await self.repo.list_by_patient(patient_id, active_only)

    async def create(self, patient_id: str, data: MedicationCreate) -> ContinuousMedication:
        if not await self.patient_repo.get_by_id(patient_id):
            raise HTTPException(status_code=404, detail="Paciente não encontrado")
        med = ContinuousMedication(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            name=data.name,
            dosage=data.dosage,
            frequency=data.frequency,
            prescribing_doctor=data.prescribing_doctor,
            started_at=data.started_at,
            notes=data.notes,
        )
        return await self.repo.create(med)

    async def deactivate(self, patient_id: str, med_id: str) -> None:
        med = await self.repo.get(med_id, patient_id)
        if not med:
            raise HTTPException(status_code=404, detail="Medicamento não encontrado")
        await self.repo.delete(med)
