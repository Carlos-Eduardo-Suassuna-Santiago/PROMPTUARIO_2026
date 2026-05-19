from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models.patient import Allergy, ContinuousMedication, Patient, Vaccine


class PatientRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, patient_id: str, load_relations: bool = False) -> Patient | None:
        q = select(Patient).where(Patient.id == patient_id, Patient.is_active == True)
        if load_relations:
            q = q.options(
                selectinload(Patient.allergies),
                selectinload(Patient.vaccines),
                selectinload(Patient.medications),
            )
        result = await self.session.execute(q)
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: str) -> Patient | None:
        result = await self.session.execute(
            select(Patient).where(Patient.user_id == user_id, Patient.is_active == True)
        )
        return result.scalar_one_or_none()

    async def list_patients(
        self,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
    ) -> tuple[list[Patient], int]:
        q = select(Patient).where(Patient.is_active == True)
        cq = select(func.count()).select_from(Patient).where(Patient.is_active == True)
        if search:
            like = f"%{search}%"
            q = q.where(Patient.full_name.ilike(like))
            cq = cq.where(Patient.full_name.ilike(like))
        total = await self.session.scalar(cq) or 0
        result = await self.session.execute(
            q.order_by(Patient.full_name).offset((page - 1) * size).limit(size)
        )
        return list(result.scalars().all()), total

    async def create(self, patient: Patient) -> Patient:
        self.session.add(patient)
        await self.session.flush()
        await self.session.refresh(patient)
        return patient

    async def update(self, patient: Patient) -> Patient:
        await self.session.flush()
        await self.session.refresh(patient)
        return patient

    async def exists_cpf(self, cpf: str, exclude_id: str | None = None) -> bool:
        q = select(func.count()).select_from(Patient).where(Patient.cpf == cpf)
        if exclude_id:
            q = q.where(Patient.id != exclude_id)
        return (await self.session.scalar(q) or 0) > 0


class AllergyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_by_patient(self, patient_id: str) -> list[Allergy]:
        result = await self.session.execute(
            select(Allergy).where(Allergy.patient_id == patient_id).order_by(Allergy.substance)
        )
        return list(result.scalars().all())

    async def get(self, allergy_id: str, patient_id: str) -> Allergy | None:
        result = await self.session.execute(
            select(Allergy).where(Allergy.id == allergy_id, Allergy.patient_id == patient_id)
        )
        return result.scalar_one_or_none()

    async def create(self, allergy: Allergy) -> Allergy:
        self.session.add(allergy)
        await self.session.flush()
        await self.session.refresh(allergy)
        return allergy

    async def delete(self, allergy: Allergy) -> None:
        await self.session.delete(allergy)
        await self.session.flush()


class VaccineRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_by_patient(self, patient_id: str) -> list[Vaccine]:
        result = await self.session.execute(
            select(Vaccine).where(Vaccine.patient_id == patient_id).order_by(Vaccine.applied_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, vaccine_id: str, patient_id: str) -> Vaccine | None:
        result = await self.session.execute(
            select(Vaccine).where(Vaccine.id == vaccine_id, Vaccine.patient_id == patient_id)
        )
        return result.scalar_one_or_none()

    async def create(self, vaccine: Vaccine) -> Vaccine:
        self.session.add(vaccine)
        await self.session.flush()
        await self.session.refresh(vaccine)
        return vaccine

    async def delete(self, vaccine: Vaccine) -> None:
        await self.session.delete(vaccine)
        await self.session.flush()


class MedicationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_by_patient(self, patient_id: str, active_only: bool = False) -> list[ContinuousMedication]:
        q = select(ContinuousMedication).where(ContinuousMedication.patient_id == patient_id)
        if active_only:
            q = q.where(ContinuousMedication.active == True)
        result = await self.session.execute(q.order_by(ContinuousMedication.name))
        return list(result.scalars().all())

    async def get(self, med_id: str, patient_id: str) -> ContinuousMedication | None:
        result = await self.session.execute(
            select(ContinuousMedication).where(
                ContinuousMedication.id == med_id,
                ContinuousMedication.patient_id == patient_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, med: ContinuousMedication) -> ContinuousMedication:
        self.session.add(med)
        await self.session.flush()
        await self.session.refresh(med)
        return med

    async def delete(self, med: ContinuousMedication) -> None:
        await self.session.delete(med)
        await self.session.flush()
