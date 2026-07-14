from __future__ import annotations

import hashlib
import io
import json
import logging
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)
from app.domain.models.clinical import (
    Appointment,
    ExamRequest,
    ExamRequestHistory,
    MedicalRecord,
    MedicalRecordHistory,
    PatientProjection,
    Prescription,
    PrescriptionHistory,
)
from app.domain.models.schemas import (
    AppointmentCreate, AppointmentCancelRequest,
    ExamRequestCreate, ExamResultUpdate,
    MedicalRecordCreate, MedicalRecordSignRequest, MedicalRecordUpdate,
    PrescriptionCreate,
)
from app.infrastructure.repositories.clinical_repository import (
    AppointmentRepository, ExamRequestRepository,
    MedicalRecordRepository, PrescriptionRepository,
)
from shared.audit import log_operation
from shared.events import (
    AppointmentCancelledEvent, AppointmentCreatedEvent,
    MedicalRecordCreatedEvent, PrescriptionGeneratedEvent,
)
from shared.events.broker import EventPublisher

logger = logging.getLogger(__name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
    )


def _ensure_s3_bucket():
    """Create the S3 prescriptions bucket if it doesn't exist."""
    try:
        s3 = _get_s3_client()
        try:
            s3.head_bucket(Bucket=settings.S3_BUCKET_PRESCRIPTIONS)
        except ClientError:
            s3.create_bucket(Bucket=settings.S3_BUCKET_PRESCRIPTIONS)
            logger.info("S3 bucket created: %s", settings.S3_BUCKET_PRESCRIPTIONS)
    except Exception as e:
        logger.warning("Could not ensure S3 bucket: %s", e)


def _sanitize_rich_notes(notes: dict | None) -> dict | None:
    """
    Sanitize rich notes by removing potentially dangerous HTML/script content.
    Only allow safe structured text in JSON format.
    """
    if notes is None:
        return None
    if not isinstance(notes, dict):
        return None

    def _sanitize_value(val):
        if isinstance(val, str):
            # Remove script tags and dangerous HTML
            import re
            val = re.sub(r'<script[^>]*>.*?</script>', '', val, flags=re.DOTALL | re.IGNORECASE)
            val = re.sub(r'on\w+\s*=\s*["\'][^"\']*["\']', '', val, flags=re.IGNORECASE)
            val = val.replace('<', '<').replace('>', '>')
            return val[:10000]  # Limit field size
        if isinstance(val, dict):
            return {k: _sanitize_value(v) for k, v in val.items()}
        if isinstance(val, list):
            return [_sanitize_value(v) for v in val]
        return val

    return {k: _sanitize_value(v) for k, v in notes.items()}


def _compute_signature_hash(record: MedicalRecord) -> str:
    """
    Compute an integrity hash from the MedicalRecord's clinical content.
    This provides a tamper-evident signature for the record.
    """
    content = {
        "id": record.id,
        "patient_id": record.patient_id,
        "doctor_id": record.doctor_id,
        "chief_complaint": record.chief_complaint,
        "anamnesis": record.anamnesis,
        "physical_exam": record.physical_exam,
        "diagnosis": record.diagnosis,
        "diagnosis_codes": record.diagnosis_codes,
        "treatment_plan": record.treatment_plan,
        "observations": record.observations,
        "rich_notes": record.rich_notes,
    }
    raw = json.dumps(content, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _generate_prescription_pdf(rx: Prescription, doctor_name: str = "Médico") -> bytes:
    """
    Generate a PDF for a prescription using a simple HTML template.
    Returns PDF bytes.
    """
    medications_html = ""
    for med in (rx.medications or []):
        name = med.get("name", "N/A")
        dosage = med.get("dosage", "N/A")
        frequency = med.get("frequency", "N/A")
        duration = med.get("duration_days", "N/A")
        instructions = med.get("instructions", "")
        medications_html += f"""
        <tr>
            <td>{name}</td>
            <td>{dosage}</td>
            <td>{frequency}</td>
            <td>{duration} dias</td>
            <td>{instructions}</td>
        </tr>"""

    import weasyprint
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8">
<style>
    body {{ font-family: Arial, sans-serif; margin: 40px; font-size: 12px; }}
    .header {{ text-align: center; margin-bottom: 30px; }}
    .header h1 {{ color: #2563eb; margin: 0; font-size: 20px; }}
    .header p {{ color: #666; margin: 5px 0; }}
    .info {{ margin-bottom: 20px; }}
    .info td {{ padding: 2px 10px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
    th {{ background: #2563eb; color: white; padding: 10px; text-align: left; }}
    td {{ border: 1px solid #ddd; padding: 8px; }}
    .footer {{ margin-top: 50px; text-align: center; color: #999; font-size: 10px; }}
    .signature {{ margin-top: 80px; }}
    .signature-line {{ border-top: 1px solid #333; width: 300px; margin: 0 auto; padding-top: 5px; text-align: center; }}
</style>
</head><body>
<div class="header">
    <h1>PROMPTUÁRIO — Prescrição Médica</h1>
    <p>ID: {rx.id}</p>
</div>
<div class="info">
    <table><tr><td><strong>Data:</strong> {rx.created_at.strftime('%d/%m/%Y %H:%M')}</td>
    <td><strong>Validade:</strong> {rx.valid_days} dias</td></tr></table>
</div>
<table>
    <thead><tr><th>Medicamento</th><th>Dosagem</th><th>Frequência</th><th>Duração</th><th>Instruções</th></tr></thead>
    <tbody>{medications_html}</tbody>
</table>
<div class="info">
    <p><strong>Instruções gerais:</strong> {rx.instructions or 'Nenhuma'}</p>
</div>
<div class="signature">
    <div class="signature-line">{doctor_name}</div>
</div>
<div class="footer">
    <p>Documento gerado eletronicamente pelo sistema Promptuário em {rx.created_at.strftime('%d/%m/%Y às %H:%M')}</p>
    <p>Hash de integridade: {rx.signature_hash or 'N/A'}</p>
</div>
</body></html>"""

    pdf_bytes = weasyprint.HTML(string=html).write_pdf()
    return pdf_bytes


def _upload_pdf_to_s3(rx_id: str, pdf_bytes: bytes) -> str | None:
    """Upload PDF bytes to S3 and return the S3 key."""
    try:
        s3 = _get_s3_client()
        s3_key = f"prescriptions/{rx_id[:2]}/{rx_id[2:4]}/{rx_id}.pdf"
        s3.put_object(
            Bucket=settings.S3_BUCKET_PRESCRIPTIONS,
            Key=s3_key,
            Body=pdf_bytes,
            ContentType="application/pdf",
        )
        return s3_key
    except ClientError as e:
        logger.error("S3 PDF upload failed: %s", e)
        return None


def _generate_certificate_pdf(cert: MedicalCertificate, doctor_name: str, patient_name: str) -> bytes:
    import weasyprint
    html = f"""<html><head>
<style>
    body {{ font-family: sans-serif; color: #333; line-height: 1.6; padding: 40px; }}
    .header h1 {{ color: #2563eb; margin: 0; font-size: 20px; }}
    .header p {{ color: #666; margin: 5px 0; }}
    .info {{ margin-bottom: 20px; }}
    .info td {{ padding: 2px 10px; }}
    .content {{ margin: 40px 0; text-align: justify; font-size: 16px; line-height: 1.8; }}
    .footer {{ margin-top: 50px; text-align: center; color: #999; font-size: 10px; }}
    .signature {{ margin-top: 80px; }}
    .signature-line {{ border-top: 1px solid #333; width: 300px; margin: 0 auto; padding-top: 5px; text-align: center; }}
</style>
</head><body>
<div class="header">
    <h1>PROMPTUÁRIO — Atestado Médico</h1>
    <p>ID: {cert.id}</p>
</div>
<div class="info">
    <table><tr><td><strong>Data de Emissão:</strong> {cert.created_at.strftime('%d/%m/%Y %H:%M')}</td></tr></table>
</div>
<div class="content">
    <p>Atesto, para os devidos fins, que o(a) paciente <strong>{patient_name}</strong> foi submetido(a) a avaliação médica nesta data ({cert.start_date.strftime('%d/%m/%Y')}) e necessita de <strong>{cert.days_off} dias de repouso</strong> por motivos de saúde.</p>
    <p><strong>Motivo / CID:</strong> {cert.reason}</p>
    {f"<p><strong>Observações:</strong> {cert.notes}</p>" if cert.notes else ""}
</div>
<div class="signature">
    <div class="signature-line">{doctor_name}</div>
</div>
<div class="footer">
    <p>Documento gerado eletronicamente pelo sistema Promptuário em {cert.created_at.strftime('%d/%m/%Y às %H:%M')}</p>
    <p>Hash de integridade: {cert.signature_hash or 'N/A'}</p>
</div>
</body></html>"""

    pdf_bytes = weasyprint.HTML(string=html).write_pdf()
    return pdf_bytes


def _upload_certificate_pdf_to_s3(cert_id: str, pdf_bytes: bytes) -> str | None:
    try:
        s3 = _get_s3_client()
        s3_key = f"certificates/{cert_id[:2]}/{cert_id[2:4]}/{cert_id}.pdf"
        s3.put_object(
            # Using the same bucket for clinical documents
            Bucket=settings.S3_BUCKET_PRESCRIPTIONS,
            Key=s3_key,
            Body=pdf_bytes,
            ContentType="application/pdf",
        )
        return s3_key
    except ClientError as e:
        logger.error("S3 Certificate PDF upload failed: %s", e)
        return None

# ─── Services ─────────────────────────────────────────────────────────────────


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

    async def list_appointments(self, page, size, patient_id, doctor_id, appt_status, from_date, to_date, patient_name=None):
        return await self.repo.list_appointments(page, size, patient_id, doctor_id, appt_status, from_date, to_date, patient_name)

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

    async def confirm(self, appt_id: str) -> Appointment:
        appt = await self.repo.get(appt_id)
        if not appt:
            raise HTTPException(status_code=404, detail="Consulta não encontrada")
        if appt.status not in ("SCHEDULED",):
            raise HTTPException(status_code=400, detail=f"Não é possível confirmar uma consulta {appt.status}")
        
        appt.status = "CONFIRMED"
        return await self.repo.update(appt)

    async def complete(self, appt_id: str) -> Appointment:
        appt = await self.get(appt_id)
        if appt.status not in ("SCHEDULED", "CONFIRMED"):
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
            diagnosis_codes=data.diagnosis_codes or [],
            treatment_plan=data.treatment_plan,
            observations=data.observations,
            rich_notes=_sanitize_rich_notes(data.rich_notes),
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
            snapshot={"chief_complaint": record.chief_complaint, "has_rich_notes": record.rich_notes is not None},
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

        if data.rich_notes is not None:
            record.rich_notes = _sanitize_rich_notes(data.rich_notes)
            changed["rich_notes"] = record.rich_notes

        # If signed, invalidate signature on update
        if record.signature_hash:
            record.signature_hash = None
            record.signed_by = None
            record.signed_at = None
            changed["signature_invalidated"] = True

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

    async def sign(self, record_id: str, doctor_id: str) -> MedicalRecord:
        """Digitally sign a medical record by computing and storing its integrity hash."""
        record = await self.repo.get(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Prontuário não encontrado")
        if record.doctor_id != doctor_id:
            raise HTTPException(status_code=403, detail="Apenas o médico responsável pode assinar")

        record.signature_hash = _compute_signature_hash(record)
        record.signed_by = doctor_id
        record.signed_at = datetime.now(timezone.utc)
        record = await self.repo.update(record)

        await self.repo.add_history(MedicalRecordHistory(
            id=str(uuid.uuid4()),
            record_id=record.id,
            changed_by=doctor_id,
            change_type="SIGNED",
            snapshot={"signature_hash": record.signature_hash, "signed_at": record.signed_at.isoformat()},
        ))
        await log_operation(
            self.repo.session,
            service="clinical-service",
            table="medical_records",
            operation="SIGN",
            record_id=record_id,
            user_id=doctor_id,
            user_role="DOCTOR",
            new_values={"signature_hash": record.signature_hash[:16]},
        )
        return record

    async def verify_signature(self, record_id: str) -> dict:
        """Verify that the stored signature matches a recomputed hash of the current content."""
        record = await self.repo.get(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Prontuário não encontrado")
        if not record.signature_hash:
            return {"verified": False, "reason": "Prontuário não assinado"}

        current_hash = _compute_signature_hash(record)
        verified = current_hash == record.signature_hash
        return {
            "verified": verified,
            "stored_hash": record.signature_hash,
            "computed_hash": current_hash,
            "signed_by": record.signed_by,
            "signed_at": record.signed_at.isoformat() if record.signed_at else None,
            "reason": "Integridade confirmada" if verified else "O conteúdo foi alterado após a assinatura",
        }

    async def list_by_patient(self, patient_id: str, page: int, size: int) -> tuple[list[MedicalRecord], int]:
        return await self.repo.list_by_patient(patient_id, page, size)

    async def list_records(self, doctor_id: str | None, page: int, size: int) -> tuple[list[MedicalRecord], int]:
        return await self.repo.list_records(doctor_id, page, size)


class PrescriptionService:
    def __init__(self, session: AsyncSession, publisher: EventPublisher, s3_client=None):
        self.record_repo = MedicalRecordRepository(session)
        self.rx_repo = PrescriptionRepository(session)
        self.session = session
        self.publisher = publisher

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

        # Generate PDF synchronously (inline) — non-blocking for a single prescription
        if settings.PDF_GENERATION_ENABLED:
            try:
                doctor_name = doctor_id  # Could be enriched from IAM projection
                pdf_bytes = _generate_prescription_pdf(rx, doctor_name=doctor_name)
                s3_key = _upload_pdf_to_s3(rx.id, pdf_bytes)

                if s3_key:
                    rx.pdf_s3_key = s3_key
                    rx.pdf_generated_at = datetime.now(timezone.utc)
                    rx.signature_hash = hashlib.sha256(pdf_bytes).hexdigest()
                    rx.signed_by = doctor_id
                    rx.signed_at = datetime.now(timezone.utc)

                    await self.session.flush()
                    await self.session.refresh(rx)
                    logger.info("Prescription PDF generated: rx=%s, s3_key=%s", rx.id, s3_key)
            except Exception as e:
                logger.error("Prescription PDF generation failed (non-fatal): %s", e)

        # Audit trail
        await self.rx_repo.add_history(PrescriptionHistory(
            id=str(uuid.uuid4()),
            prescription_id=rx.id,
            record_id=record_id,
            changed_by=doctor_id,
            change_type="CREATED",
            snapshot={
                "medications_count": len(rx.medications),
                "has_pdf": rx.pdf_s3_key is not None,
            },
        ))

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
                "has_pdf": rx.pdf_s3_key is not None,
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
                pdf_s3_key=rx.pdf_s3_key,
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

    async def get_pdf_download_url(self, prescription_id: str) -> str:
        rx = await self.rx_repo.get(prescription_id)
        if not rx:
            raise HTTPException(status_code=404, detail="Prescrição não encontrada")
        if not rx.pdf_s3_key:
            raise HTTPException(status_code=400, detail="PDF ainda não foi gerado para esta prescrição")

        try:
            s3 = _get_s3_client()
            url = s3.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.S3_BUCKET_PRESCRIPTIONS,
                    "Key": rx.pdf_s3_key,
                    "ResponseContentDisposition": f'inline; filename="prescricao_{rx.id}.pdf"',
                },
                ExpiresIn=settings.S3_PRESIGNED_URL_EXPIRY,
            )
            if "http://minio:9000" in url:
                url = url.replace("http://minio:9000", settings.S3_PUBLIC_ENDPOINT)
            elif settings.S3_ENDPOINT in url and hasattr(settings, "S3_PUBLIC_ENDPOINT") and settings.S3_PUBLIC_ENDPOINT:
                url = url.replace(settings.S3_ENDPOINT, settings.S3_PUBLIC_ENDPOINT)
            return url
        except ClientError as e:
            logger.error("S3 pre-signed URL generation failed: %s", e)
            raise HTTPException(status_code=500, detail="Falha ao gerar URL de download do PDF")


class ExamRequestService:
    def __init__(self, session: AsyncSession):
        self.record_repo = MedicalRecordRepository(session)
        self.exam_repo = ExamRequestRepository(session)
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

        # Audit trail
        await self.exam_repo.add_history(ExamRequestHistory(
            id=str(uuid.uuid4()),
            exam_id=exam.id,
            record_id=record_id,
            changed_by=doctor_id,
            change_type="CREATED",
            snapshot={
                "exam_type": exam.exam_type,
                "urgency": exam.urgency,
            },
        ))
        await log_operation(
            self.session,
            service="clinical-service",
            table="exam_requests",
            operation="INSERT",
            record_id=exam.id,
            user_id=doctor_id,
            user_role="DOCTOR",
            new_values={
                "exam_type": exam.exam_type,
                "urgency": exam.urgency,
                "record_id": record_id,
            },
        )
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

        old_result = exam.result
        exam.result = data.result
        exam.result_date = data.result_date or datetime.now(timezone.utc)
        await self.session.flush()

        # Audit trail
        await self.exam_repo.add_history(ExamRequestHistory(
            id=str(uuid.uuid4()),
            exam_id=exam.id,
            record_id=record_id,
            changed_by=doctor_id,
            change_type="RESULT_RECORDED",
            snapshot={
                "has_result": bool(data.result),
                "result_date": exam.result_date.isoformat() if exam.result_date else None,
            },
        ))
        await log_operation(
            self.session,
            service="clinical-service",
            table="exam_requests",
            operation="UPDATE",
            record_id=exam.id,
            user_id=doctor_id,
            user_role="DOCTOR",
            old_values={"has_result": bool(old_result)},
            new_values={"has_result": bool(data.result)},
        )
        return exam


class MedicalCertificateService:
    def __init__(self, session: AsyncSession):
        self.record_repo = MedicalRecordRepository(session)
        self.cert_repo = MedicalCertificateRepository(session)
        self.session = session

    async def create(self, record_id: str, data: MedicalCertificateCreate, doctor_id: str) -> MedicalCertificate:
        record = await self.record_repo.get(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Prontuário não encontrado")
        if record.doctor_id != doctor_id:
            raise HTTPException(status_code=403, detail="Acesso negado")

        cert = MedicalCertificate(
            id=str(uuid.uuid4()),
            record_id=record_id,
            patient_id=record.patient_id,
            doctor_id=doctor_id,
            reason=data.reason,
            days_off=data.days_off,
            start_date=data.start_date,
            notes=data.notes,
        )

        # Buscar nome do paciente ANTES do commit (a sessão expira após commit)
        patient_name = "Paciente"
        try:
            from sqlalchemy import select as _select
            from app.domain.models.clinical import PatientProjection
            proj_result = await self.session.execute(
                _select(PatientProjection).where(PatientProjection.id == record.patient_id)
            )
            proj = proj_result.scalar_one_or_none()
            if proj:
                patient_name = proj.full_name
        except Exception:
            logger.warning("Não foi possível buscar nome do paciente para atestado %s", cert.id)

        self.session.add(cert)
        await self.session.flush()
        await self.session.refresh(cert)

        if settings.PDF_GENERATION_ENABLED:
            try:
                doctor_name = doctor_id
                pdf_bytes = _generate_certificate_pdf(cert, doctor_name=doctor_name, patient_name=patient_name)
                s3_key = _upload_certificate_pdf_to_s3(cert.id, pdf_bytes)

                if s3_key:
                    cert.pdf_s3_key = s3_key
                    cert.pdf_generated_at = datetime.now(timezone.utc)
                    import hashlib
                    cert.signature_hash = hashlib.sha256(pdf_bytes).hexdigest()
                    cert.signed_by = doctor_id
                    cert.signed_at = datetime.now(timezone.utc)

                    await self.session.flush()
                    await self.session.refresh(cert)
                    logger.info("Certificate PDF generated: cert=%s, s3_key=%s", cert.id, s3_key)
            except Exception as e:
                logger.error("Certificate PDF generation failed (non-fatal): %s", e)

        # Audit trail
        await self.cert_repo.add_history(MedicalCertificateHistory(
            id=str(uuid.uuid4()),
            certificate_id=cert.id,
            record_id=record_id,
            changed_by=doctor_id,
            change_type="CREATED",
            snapshot={
                "days_off": cert.days_off,
                "has_pdf": cert.pdf_s3_key is not None,
            },
        ))

        await log_operation(
            self.session,
            service="clinical-service",
            table="medical_certificates",
            operation="INSERT",
            record_id=cert.id,
            user_id=doctor_id,
            user_role="DOCTOR",
            new_values={
                "record_id": record_id,
                "days_off": cert.days_off,
                "has_pdf": cert.pdf_s3_key is not None,
            },
        )
        await self.session.commit()
        return cert

    async def get_pdf_download_url(self, certificate_id: str) -> str:
        cert = await self.cert_repo.get(certificate_id)
        if not cert:
            raise HTTPException(status_code=404, detail="Atestado não encontrado")
        if not cert.pdf_s3_key:
            raise HTTPException(status_code=400, detail="PDF ainda não foi gerado para este atestado")

        try:
            s3 = _get_s3_client()
            url = s3.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.S3_BUCKET_PRESCRIPTIONS,
                    "Key": cert.pdf_s3_key,
                    "ResponseContentDisposition": f'inline; filename="atestado_{cert.id}.pdf"',
                },
                ExpiresIn=settings.S3_PRESIGNED_URL_EXPIRY,
            )
            if "http://minio:9000" in url:
                url = url.replace("http://minio:9000", settings.S3_PUBLIC_ENDPOINT)
            elif settings.S3_ENDPOINT in url and hasattr(settings, "S3_PUBLIC_ENDPOINT") and settings.S3_PUBLIC_ENDPOINT:
                url = url.replace(settings.S3_ENDPOINT, settings.S3_PUBLIC_ENDPOINT)
            return url
        except ClientError as e:
            logger.error("S3 pre-signed URL generation failed: %s", e)
            raise HTTPException(status_code=500, detail="Falha ao gerar URL de download do PDF")

