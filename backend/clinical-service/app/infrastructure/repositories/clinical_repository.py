from __future__ import annotations

from datetime import date, datetime
from typing import Sequence

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models.clinical import (
    Appointment, DoctorSchedule, ExamRequest,
    ExamRequestHistory, MedicalRecord, MedicalRecordHistory,
    PatientProjection, Prescription, PrescriptionHistory, TimeSlot,
)


class AppointmentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, appt_id: str) -> Appointment | None:
        result = await self.session.execute(
            select(Appointment).where(Appointment.id == appt_id)
        )
        return result.scalar_one_or_none()

    async def list_appointments(
        self,
        page: int = 1,
        size: int = 20,
        patient_id: str | None = None,
        doctor_id: str | None = None,
        status: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> tuple[list[Appointment], int]:
        q = select(Appointment)
        cq = select(func.count()).select_from(Appointment)
        filters = []
        if patient_id:
            filters.append(Appointment.patient_id == patient_id)
        if doctor_id:
            filters.append(Appointment.doctor_id == doctor_id)
        if status:
            filters.append(Appointment.status == status)
        if from_date:
            filters.append(Appointment.scheduled_at >= datetime.combine(from_date, datetime.min.time()))
        if to_date:
            filters.append(Appointment.scheduled_at <= datetime.combine(to_date, datetime.max.time()))
        if filters:
            q = q.where(and_(*filters))
            cq = cq.where(and_(*filters))
        total = await self.session.scalar(cq) or 0
        result = await self.session.execute(
            q.order_by(Appointment.scheduled_at.desc())
            .offset((page - 1) * size).limit(size)
        )
        return list(result.scalars().all()), total

    async def check_slot_conflict(self, doctor_id: str, scheduled_at: datetime, exclude_id: str | None = None) -> bool:
        """Returns True if there's already an active appointment within 30min of scheduled_at."""
        from datetime import timedelta
        window_start = scheduled_at - timedelta(minutes=30)
        window_end = scheduled_at + timedelta(minutes=30)
        q = select(func.count()).select_from(Appointment).where(
            Appointment.doctor_id == doctor_id,
            Appointment.scheduled_at.between(window_start, window_end),
            Appointment.status.in_(["SCHEDULED", "CONFIRMED"]),
        )
        if exclude_id:
            q = q.where(Appointment.id != exclude_id)
        return (await self.session.scalar(q) or 0) > 0

    async def create(self, appt: Appointment) -> Appointment:
        self.session.add(appt)
        await self.session.flush()
        await self.session.refresh(appt)
        await self.session.commit()
        return appt

    async def update(self, appt: Appointment) -> Appointment:
        await self.session.flush()
        await self.session.refresh(appt)
        await self.session.commit()
        return appt


class MedicalRecordRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, record_id: str, load_relations: bool = False) -> MedicalRecord | None:
        q = select(MedicalRecord).where(MedicalRecord.id == record_id)
        if load_relations:
            q = q.options(
                selectinload(MedicalRecord.prescriptions),
                selectinload(MedicalRecord.exam_requests),
                selectinload(MedicalRecord.history),
            )
        result = await self.session.execute(q)
        return result.scalar_one_or_none()

    async def get_by_appointment(self, appointment_id: str) -> MedicalRecord | None:
        result = await self.session.execute(
            select(MedicalRecord).where(MedicalRecord.appointment_id == appointment_id)
        )
        return result.scalar_one_or_none()

    async def list_by_patient(self, patient_id: str, page: int, size: int) -> tuple[list[MedicalRecord], int]:
        total = await self.session.scalar(
            select(func.count()).select_from(MedicalRecord).where(MedicalRecord.patient_id == patient_id)
        ) or 0
        result = await self.session.execute(
            select(MedicalRecord)
            .where(MedicalRecord.patient_id == patient_id)
            .order_by(MedicalRecord.created_at.desc())
            .offset((page - 1) * size).limit(size)
        )
        return list(result.scalars().all()), total

    async def list_records(self, doctor_id: str | None, page: int, size: int) -> tuple[list[MedicalRecord], int]:
        query = select(MedicalRecord)
        if doctor_id:
            query = query.where(MedicalRecord.doctor_id == doctor_id)
        
        total_query = select(func.count()).select_from(MedicalRecord)
        if doctor_id:
            total_query = total_query.where(MedicalRecord.doctor_id == doctor_id)

        total = await self.session.scalar(total_query) or 0
        result = await self.session.execute(
            query.order_by(MedicalRecord.created_at.desc()).offset((page - 1) * size).limit(size)
        )
        return list(result.scalars().all()), total

    async def create(self, record: MedicalRecord) -> MedicalRecord:
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        await self.session.commit()
        return record

    async def update(self, record: MedicalRecord) -> MedicalRecord:
        await self.session.flush()
        await self.session.refresh(record)
        await self.session.commit()
        return record

    async def add_history(self, history: MedicalRecordHistory) -> None:
        self.session.add(history)
        await self.session.flush()
        await self.session.commit()


class PrescriptionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, prescription_id: str) -> Prescription | None:
        result = await self.session.execute(
            select(Prescription).where(Prescription.id == prescription_id)
        )
        return result.scalar_one_or_none()

    async def update(self, rx: Prescription) -> Prescription:
        await self.session.flush()
        await self.session.refresh(rx)
        await self.session.commit()
        return rx

    async def add_history(self, history: PrescriptionHistory) -> None:
        self.session.add(history)
        await self.session.flush()
        await self.session.commit()


class ExamRequestRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, exam_id: str) -> ExamRequest | None:
        result = await self.session.execute(
            select(ExamRequest).where(ExamRequest.id == exam_id)
        )
        return result.scalar_one_or_none()

    async def add_history(self, history: ExamRequestHistory) -> None:
        self.session.add(history)
        await self.session.flush()
        await self.session.commit()


class PatientProjectionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, projection: PatientProjection) -> None:
        existing = await self.session.get(PatientProjection, projection.id)
        if existing:
            existing.full_name = projection.full_name
            existing.phone = projection.phone
            existing.date_of_birth = projection.date_of_birth
            existing.blood_type = projection.blood_type
        else:
            self.session.add(projection)
        await self.session.flush()
        await self.session.commit()