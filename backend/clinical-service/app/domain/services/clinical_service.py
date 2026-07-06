from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)
from app.domain.models.clinical import (
    Appointment, ExamRequest, MedicalRecord,
    MedicalRecordHistory, PatientProjection, Prescription,
)
from app.domain.models.schemas import (
    AppointmentCreate, AppointmentCancelRequest,
    ExamRequestCreate, ExamResultUpdate,
    MedicalRecordCreate, MedicalRecordUpdate,
    PrescriptionCreate,
)
from app.infrastructure.repositories.clinical_repository import (
    AppointmentRepository, MedicalRecordRepository,
)
from shared.audit import log_operation
from shared.events import (
    AppointmentCancelledEvent, AppointmentCreatedEvent,
    MedicalRecordCreatedEvent, PrescriptionGeneratedEvent,
)
from shared.events.broker import EventPublisher


class AppointmentService:
    def __init__(self, session: AsyncSession, publisher: EventPublisher):
        self.repo = AppointmentRepository(session)
        self.publisher = publisher

    async def create(self, data: AppointmentCreate, created_by: str) -> Appointment:
        if await self.repo.check_slot_conflict(data.doctor_id, data.scheduled_at):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Médico já possui consulta nesse horário",
            )
        appt = Appointment(
            id=str(uuid.uuid4()),
            patient_id=data.patient_id,
            doctor_id=data.doctor_id,
            slot_id=data.slot_id,
            scheduled_at=data.scheduled_at,
            appointment_type=data.appointment_type,
            specialty=data.specialty,
            notes=data.notes,
            created_by=created_by,
        )
        appt = await self.repo.create(appt)
        await self.publisher.publish(
            AppointmentCreatedEvent(
                appointment_id=appt.id,
                patient_id=appt.patient_id,
                doctor_id=appt.doctor_id,
                scheduled_at=appt.scheduled_at,
                appointment_type=appt.appointment_type,
                specialty=appt.specialty,
            )
        )
        await log_operation(
            self.repo.session,
            service="clinical-service",
            table="appointments",
            operation="INSERT",
            record_id=appt.id,
            user_id=created_by,
            new_values={
                "patient_id": appt.patient_id,
                "doctor_id": appt.doctor_id,
                "scheduled_at": appt.scheduled_at.isoformat(),
            },
        )
        return appt

    async def get(self, appt_id: str) -> Appointment:
        appt = await self.repo.get(appt_id)
        if not appt:
            raise HTTPException(status_code=404, detail="Consulta não encontrada")
        return appt

    async def list_appointments(self, page, size, patient_id, doctor_id, appt_status, from_date, to_date):
        return await self.repo.list_appointments(page, size, patient_id, doctor_id, appt_status, from_date, to_date)

    async def cancel(self, appt_id: str, body: AppointmentCancelRequest, cancelled_by: str, user_role: str) -> Appointment:
        appt = await self.get(appt_id)

        if appt.status not in ("SCHEDULED", "CONFIRMED"):
            raise HTTPException(status_code=400, detail="Consulta não pode ser cancelada nesse status")

        now = datetime.now(timezone.utc)
        hours_before = (appt.scheduled_at.replace(tzinfo=timezone.utc) - now).total_seconds() / 3600
        policy_violated = hours_before < settings.APPOINTMENT_CANCEL_HOURS_MIN

        if policy_violated and user_role == "PATIENT":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cancelamento deve ser feito com no mínimo {settings.APPOINTMENT_CANCEL_HOURS_MIN}h de antecedência",
            )

        appt.status = "CANCELLED"
        appt.cancellation_reason = body.reason
        appt.cancelled_by = cancelled_by
        appt.cancelled_at = now
        appt = await self.repo.update(appt)

        await self.publisher.publish(
            AppointmentCancelledEvent(
                appointment_id=appt.id,
                cancelled_by=cancelled_by,
                cancellation_reason=body.reason,
                hours_before=hours_before,
                policy_violated=policy_violated,
            )
        )
        await log_operation(
            self.repo.session,
            service="clinical-service",
            table="appointments",
            operation="UPDATE",
            record_id=appt_id,
            user_id=cancelled_by,
            old_values={"status": "SCHEDULED"},
            new_values={"status": "CANCELLED", "reason": body.reason},
        )
        return appt

    async def complete(self, appt_id: str) -> Appointment:
        appt = await self.get(appt_id)
        if appt.status != "SCHEDULED" and appt.status != "CONFIRMED":
            raise HTTPException(status_code=400, detail="Status inválido para conclusão")
        appt.status = "COMPLETED"
        return await self.repo.update(appt)


class MedicalRecordService:
    def __init__(self, session: AsyncSession, publisher: EventPublisher):
        self.repo = MedicalRecordRepository(session)
        self.appt_repo = AppointmentRepository(session)
        self.publisher = publisher

    async def create(self, data: MedicalRecordCreate, doctor_id: str) -> MedicalRecord:
        appt = await self.appt_repo.get(data.appointment_id)
        if not appt:
            raise HTTPException(status_code=404, detail="Consulta não encontrada")
        if appt.doctor_id != doctor_id:
            raise HTTPException(status_code=403, detail="Médico não associado a esta consulta")
        if await self.repo.get_by_appointment(data.appointment_id):
            raise HTTPException(status_code=409, detail="Prontuário já existe para esta consulta")

        record = MedicalRecord(
            id=str(uuid.uuid4()),
            appointment_id=data.appointment_id,
            patient_id=appt.patient_id,
            doctor_id=doctor_id,
            chief_complaint=data.chief_complaint,
            anamnesis=data.anamnesis,
            physical_exam=data.physical_exam,
            diagnosis=data.diagnosis,
            diagnosis_codes=data.diagnosis_codes,
            treatment_plan=data.treatment_plan,
            observations=data.observations,
        )
        record = await self.repo.create(record)

        # Mark appointment complete
        appt.status = "COMPLETED"
        await self.appt_repo.update(appt)

        # Audit
        await self.repo.add_history(MedicalRecordHistory(
            id=str(uuid.uuid4()),
            record_id=record.id,
            changed_by=doctor_id,
            change_type="CREATED",
            snapshot={"chief_complaint": record.chief_complaint},
        ))

        await self.publisher.publish(
            MedicalRecordCreatedEvent(
                record_id=record.id,
                appointment_id=record.appointment_id,
                patient_id=record.patient_id,
                doctor_id=record.doctor_id,
                chief_complaint=record.chief_complaint,
                diagnosis_codes=record.diagnosis_codes or [],
            )
        )
        await log_operation(
            self.repo.session,
            service="clinical-service",
            table="medical_records",
            operation="INSERT",
            record_id=record.id,
            user_id=doctor_id,
            user_role="DOCTOR",
            new_values={
                "patient_id": record.patient_id,
                "chief_complaint": record.chief_complaint[:100],
            },
        )
        return record

    async def get(self, record_id: str, user_id: str, role: str) -> MedicalRecord:
        record = await self.repo.get(record_id, load_relations=True)
        if not record:
            raise HTTPException(status_code=404, detail="Prontuário não encontrado")
        # PATIENT can only view their own records
        if role == "PATIENT":
            from app.infrastructure.repositories.clinical_repository import PatientProjectionRepository
            # We resolve patient_id from projection or appointment
            if record.patient_id != user_id:
                raise HTTPException(status_code=403, detail="Acesso negado")
        return record

    async def update(self, record_id: str, data: MedicalRecordUpdate, doctor_id: str) -> MedicalRecord:
        record = await self.repo.get(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Prontuário não encontrado")
        if record.doctor_id != doctor_id:
            raise HTTPException(status_code=403, detail="Apenas o médico responsável pode editar")

        changed = {}
        for field in ("chief_complaint", "anamnesis", "physical_exam", "diagnosis",
                      "diagnosis_codes", "treatment_plan", "observations"):
            val = getattr(data, field)
            if val is not None:
                setattr(record, field, val)
                changed[field] = val

        record = await self.repo.update(record)
        if changed:
            await self.repo.add_history(MedicalRecordHistory(
                id=str(uuid.uuid4()),
                record_id=record.id,
                changed_by=doctor_id,
                change_type="UPDATED",
                snapshot=changed,
            ))
            await log_operation(
                self.repo.session,
                service="clinical-service",
                table="medical_records",
                operation="UPDATE",
                record_id=record_id,
                user_id=doctor_id,
                user_role="DOCTOR",
                new_values={"changed_fields": list(changed.keys())},
            )
        return record

    async def list_by_patient(self, patient_id: str, page: int, size: int):
        return await self.repo.list_by_patient(patient_id, page, size)


class PrescriptionService:
    def __init__(self, session: AsyncSession, publisher: EventPublisher, s3_client=None):
        self.record_repo = MedicalRecordRepository(session)
        self.session = session
        self.publisher = publisher
        self.s3 = s3_client

    async def create(self, record_id: str, data: PrescriptionCreate, doctor_id: str) -> Prescription:
        record = await self.record_repo.get(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Prontuário não encontrado")
        if record.doctor_id != doctor_id:
            raise HTTPException(status_code=403, detail="Acesso negado")

        rx = Prescription(
            id=str(uuid.uuid4()),
            record_id=record_id,
            patient_id=record.patient_id,
            doctor_id=doctor_id,
            medications=[m.model_dump() for m in data.medications],
            instructions=data.instructions,
            valid_days=data.valid_days,
        )
        # Buscar nome do paciente ANTES do commit (a sessão expira após commit)
        patient_name = "Paciente"
        try:
            from sqlalchemy import select as _select
            proj_result = await self.session.execute(
                _select(PatientProjection).where(PatientProjection.id == record.patient_id)
            )
            proj = proj_result.scalar_one_or_none()
            if proj:
                patient_name = proj.full_name
        except Exception:
            logger.warning("Não foi possível buscar nome do paciente para prescrição %s", rx.id)

        self.session.add(rx)
        await self.session.flush()
        await self.session.refresh(rx)

        await log_operation(
            self.session,
            service="clinical-service",
            table="prescriptions",
            operation="INSERT",
            record_id=rx.id,
            user_id=doctor_id,
            user_role="DOCTOR",
            new_values={
                "record_id": record_id,
                "medications_count": len(rx.medications),
            },
        )
        await self.session.commit()

        # Publish event
        await self.publisher.publish(
            PrescriptionGeneratedEvent(
                prescription_id=rx.id,
                record_id=record_id,
                patient_id=record.patient_id,
                doctor_id=doctor_id,
                medications=rx.medications,
            )
        )

        # Disparar geração assíncrona do PDF via Celery (já tem o nome do paciente)
        try:
            from app.workers.prescription_tasks import generate_prescription_pdf

            generate_prescription_pdf.delay(
                prescription_id=rx.id,
                patient_name=patient_name,
                doctor_name=doctor_id,
                medications=rx.medications,
                instructions=rx.instructions,
                valid_days=rx.valid_days,
            )
        except Exception:
            logger.exception("Falha ao disparar task Celery para prescrição %s", rx.id)

        return rx


class ExamRequestService:
    def __init__(self, session: AsyncSession):
        self.record_repo = MedicalRecordRepository(session)
        self.session = session

    async def create(self, record_id: str, data: ExamRequestCreate, doctor_id: str) -> ExamRequest:
        record = await self.record_repo.get(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Prontuário não encontrado")
        if record.doctor_id != doctor_id:
            raise HTTPException(status_code=403, detail="Acesso negado")

        exam = ExamRequest(
            id=str(uuid.uuid4()),
            record_id=record_id,
            patient_id=record.patient_id,
            doctor_id=doctor_id,
            exam_type=data.exam_type,
            urgency=data.urgency,
            instructions=data.instructions,
        )
        self.session.add(exam)
        await self.session.flush()
        await self.session.refresh(exam)
        await self.session.commit()
        return exam

    async def record_result(self, record_id: str, exam_id: str, data: ExamResultUpdate, doctor_id: str) -> ExamRequest:
        from sqlalchemy import select
        result = await self.session.execute(
            select(ExamRequest).where(
                ExamRequest.id == exam_id,
                ExamRequest.record_id == record_id,
            )
        )
        exam = result.scalar_one_or_none()
        if not exam:
            raise HTTPException(status_code=404, detail="Solicitação de exame não encontrada")
        exam.result = data.result
        exam.result_date = data.result_date or datetime.now(timezone.utc)
        await self.session.flush()
        return exam
