from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domain.models.patient import (
    Allergy,
    ContinuousMedication,
    MedicationHistory,
    Patient,
    PatientDocument,
    Vaccine,
)
from app.domain.models.schemas import (
    AllergyCreate,
    MedicationCreate,
    MedicationDeactivate,
    MedicationUpdate,
    PatientCreate,
    PatientUpdate,
    VaccineCreate,
)
from app.infrastructure.repositories.patient_repository import (
    AllergyRepository,
    DocumentRepository,
    MedicationHistoryRepository,
    MedicationRepository,
    PatientRepository,
    VaccineRepository,
)
from shared.audit import log_operation
from shared.events import AllergyAddedEvent, PatientCreatedEvent, PatientUpdatedEvent
from shared.events.broker import EventPublisher

logger = logging.getLogger(__name__)


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
    )


def _ensure_s3_bucket():
    """Create the S3 bucket if it doesn't exist."""
    try:
        s3 = _get_s3_client()
        try:
            s3.head_bucket(Bucket=settings.S3_BUCKET_PATIENT_DOCUMENTS)
        except ClientError:
            s3.create_bucket(Bucket=settings.S3_BUCKET_PATIENT_DOCUMENTS)
            logger.info("S3 bucket created: %s", settings.S3_BUCKET_PATIENT_DOCUMENTS)
    except Exception as e:
        logger.warning("Could not ensure S3 bucket: %s", e)


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
        await log_operation(
            self.repo.session,
            service="patient-service",
            table="patients",
            operation="INSERT",
            record_id=patient.id,
            new_values={"user_id": patient.user_id, "full_name": patient.full_name},
        )
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
        """Lightweight read-model for Clinical Service — documents NOT included."""
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
            await log_operation(
                self.repo.session,
                service="patient-service",
                table="patients",
                operation="UPDATE",
                record_id=patient_id,
                user_id=current_user_id,
                new_values={"changed_fields": changed},
            )
            await self.publisher.publish(
                PatientUpdatedEvent(
                    patient_id=patient.id,
                    changed_fields=changed,
                    phone=patient.phone,
                )
            )
        return patient

    async def deactivate(self, patient_id: str) -> None:
        patient = await self.repo.get_by_id_include_inactive(patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Paciente não encontrado")
        patient.is_active = False
        await self.repo.update(patient)
        await log_operation(
            self.repo.session,
            service="patient-service",
            table="patients",
            operation="DELETE",
            record_id=patient_id,
            new_values={"is_active": False},
        )

    async def anonymize(self, patient_id: str) -> None:
        """LGPD right-to-erasure: replace PII with hashed tokens and hide documents."""
        patient = await self.repo.get_by_id_include_inactive(patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Paciente não encontrado")

        hash_suffix = hashlib.sha256(patient.id.encode()).hexdigest()[:8]
        patient.full_name = f"ANONYMIZED_{hash_suffix}"
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
        await log_operation(
            self.repo.session,
            service="patient-service",
            table="patients",
            operation="DELETE",
            record_id=patient_id,
            new_values={"anonymized": True, "lgpd_reason": "RIGHT_TO_ERASURE"},
        )

        # Soft-delete all active documents
        doc_repo = DocumentRepository(self.repo.session)
        docs, _ = await doc_repo.list_by_patient(patient_id, page=1, size=1000)
        for doc in docs:
            await doc_repo.soft_delete(doc)
        logger.info("Patient %s anonymized: %d documents soft-deleted", patient_id, len(docs))


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
        await log_operation(
            self.repo.session,
            service="patient-service",
            table="allergies",
            operation="INSERT",
            record_id=allergy.id,
            new_values={"substance": allergy.substance, "severity": allergy.severity},
        )
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
        await log_operation(
            self.repo.session,
            service="patient-service",
            table="allergies",
            operation="DELETE",
            record_id=allergy_id,
        )
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
        self.history_repo = MedicationHistoryRepository(session)
        self.patient_repo = PatientRepository(session)

    async def list(self, patient_id: str, active_only: bool = False) -> list[ContinuousMedication]:
        return await self.repo.list_by_patient(patient_id, active_only)

    async def get_history(self, patient_id: str, medication_id: str | None = None) -> list[MedicationHistory]:
        if medication_id:
            return await self.history_repo.list_by_medication(medication_id)
        return await self.history_repo.list_by_patient(patient_id)

    async def create(self, patient_id: str, data: MedicationCreate, changed_by: str | None = None) -> ContinuousMedication:
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
            version=1,
        )
        med = await self.repo.create(med)

        # Record history snapshot
        history = MedicationHistory(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            medication_id=med.id,
            name=med.name,
            dosage=med.dosage,
            frequency=med.frequency,
            prescribing_doctor=med.prescribing_doctor,
            started_at=med.started_at,
            notes=med.notes,
            active=med.active,
            version=1,
            change_type="CREATED",
            changed_by=changed_by,
        )
        await self.history_repo.create(history)
        return med

    async def update(self, patient_id: str, med_id: str, data: MedicationUpdate, changed_by: str | None = None) -> ContinuousMedication:
        med = await self.repo.get(med_id, patient_id)
        if not med:
            raise HTTPException(status_code=404, detail="Medicamento não encontrado")

        # Snapshot current state before updating
        old_version = med.version

        if data.dosage is not None:
            med.dosage = data.dosage
        if data.frequency is not None:
            med.frequency = data.frequency
        if data.prescribing_doctor is not None:
            med.prescribing_doctor = data.prescribing_doctor
        if data.notes is not None:
            med.notes = data.notes
        med.version += 1

        med = await self.repo.update(med)

        # Record history snapshot of new version
        history = MedicationHistory(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            medication_id=med.id,
            name=med.name,
            dosage=med.dosage,
            frequency=med.frequency,
            prescribing_doctor=med.prescribing_doctor,
            started_at=med.started_at,
            ended_at=med.ended_at,
            end_reason=med.end_reason,
            notes=med.notes,
            active=med.active,
            version=med.version,
            change_type="UPDATED",
            changed_by=changed_by,
        )
        await self.history_repo.create(history)
        return med

    async def deactivate(self, patient_id: str, med_id: str, data: MedicationDeactivate | None = None, changed_by: str | None = None) -> ContinuousMedication:
        med = await self.repo.get(med_id, patient_id)
        if not med:
            raise HTTPException(status_code=404, detail="Medicamento não encontrado")

        med.active = False
        med.ended_at = data.ended_at if data and data.ended_at else datetime.now(timezone.utc).date()
        med.end_reason = data.end_reason if data and data.end_reason else None
        med.version += 1
        med = await self.repo.update(med)

        # Record history snapshot
        history = MedicationHistory(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            medication_id=med.id,
            name=med.name,
            dosage=med.dosage,
            frequency=med.frequency,
            prescribing_doctor=med.prescribing_doctor,
            started_at=med.started_at,
            ended_at=med.ended_at,
            end_reason=med.end_reason,
            notes=med.notes,
            active=med.active,
            version=med.version,
            change_type="DEACTIVATED",
            changed_by=changed_by,
        )
        await self.history_repo.create(history)
        return med

    async def reactivate(self, patient_id: str, med_id: str, changed_by: str | None = None) -> ContinuousMedication:
        med = await self.repo.get(med_id, patient_id)
        if not med:
            raise HTTPException(status_code=404, detail="Medicamento não encontrado")

        med.active = True
        med.ended_at = None
        med.end_reason = None
        med.version += 1
        med = await self.repo.update(med)

        history = MedicationHistory(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            medication_id=med.id,
            name=med.name,
            dosage=med.dosage,
            frequency=med.frequency,
            prescribing_doctor=med.prescribing_doctor,
            started_at=med.started_at,
            notes=med.notes,
            active=med.active,
            version=med.version,
            change_type="REACTIVATED",
            changed_by=changed_by,
        )
        await self.history_repo.create(history)
        return med


class DocumentService:
    def __init__(self, session: AsyncSession, publisher: EventPublisher):
        self.repo = DocumentRepository(session)
        self.patient_repo = PatientRepository(session)
        self.publisher = publisher

    async def _check_patient(self, patient_id: str) -> None:
        p = await self.patient_repo.get_by_id(patient_id)
        if not p:
            raise HTTPException(status_code=404, detail="Paciente não encontrado")
        if p.anonymized:
            raise HTTPException(status_code=403, detail="Paciente anonimizado — operação não permitida")

    async def upload(
        self,
        patient_id: str,
        file: UploadFile,
        document_type: str,
        description: str | None = None,
        uploaded_by: str | None = None,
    ) -> PatientDocument:
        await self._check_patient(patient_id)

        # Validate mime type
        if file.content_type not in settings.ALLOWED_DOCUMENT_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de arquivo não permitido: {file.content_type}. "
                       f"Permitidos: {', '.join(settings.ALLOWED_DOCUMENT_MIME_TYPES)}",
            )

        # Read file content
        content = await file.read()
        file_size = len(content)

        # Validate file size
        max_bytes = settings.MAX_DOCUMENT_SIZE_MB * 1024 * 1024
        if file_size > max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"Arquivo muito grande. Máximo permitido: {settings.MAX_DOCUMENT_SIZE_MB}MB",
            )

        # Compute hash
        file_hash = hashlib.sha256(content).hexdigest()

        # Generate S3 key
        doc_id = str(uuid.uuid4())
        s3_key = f"patients/{patient_id}/documents/{doc_id}_{file.filename}"

        # Upload to S3
        try:
            s3 = _get_s3_client()
            s3.put_object(
                Bucket=settings.S3_BUCKET_PATIENT_DOCUMENTS,
                Key=s3_key,
                Body=content,
                ContentType=file.content_type,
            )
        except ClientError as e:
            logger.error("S3 upload failed: %s", e)
            raise HTTPException(status_code=500, detail="Falha ao fazer upload do arquivo")

        # Save metadata to DB
        doc = PatientDocument(
            id=doc_id,
            patient_id=patient_id,
            document_type=document_type,
            file_name=file.filename or "unknown",
            s3_key=s3_key,
            file_size=file_size,
            mime_type=file.content_type or "application/octet-stream",
            file_hash=file_hash,
            description=description,
            uploaded_by=uploaded_by,
        )
        doc = await self.repo.create(doc)
        logger.info(
            "Document uploaded: patient=%s, doc=%s, type=%s, size=%d, s3_key=%s",
            patient_id, doc.id, document_type, file_size, s3_key,
        )
        return doc

    async def list(
        self,
        patient_id: str,
        page: int = 1,
        size: int = 20,
        document_type: str | None = None,
    ) -> tuple[list[PatientDocument], int]:
        await self._check_patient(patient_id)
        return await self.repo.list_by_patient(patient_id, page, size, document_type)

    async def get(self, patient_id: str, document_id: str) -> PatientDocument:
        doc = await self.repo.get(document_id, patient_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Documento não encontrado")
        return doc

    async def get_download_url(self, patient_id: str, document_id: str) -> str:
        doc = await self.get(patient_id, document_id)
        try:
            s3 = _get_s3_client()
            url = s3.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.S3_BUCKET_PATIENT_DOCUMENTS,
                    "Key": doc.s3_key,
                    "ResponseContentDisposition": f'attachment; filename="{doc.file_name}"',
                },
                ExpiresIn=settings.S3_PRESIGNED_URL_EXPIRY,
            )
            return url
        except ClientError as e:
            logger.error("S3 pre-signed URL generation failed: %s", e)
            raise HTTPException(status_code=500, detail="Falha ao gerar URL de download")

    async def soft_delete(self, patient_id: str, document_id: str) -> None:
        await self._check_patient(patient_id)
        doc = await self.get(patient_id, document_id)
        await self.repo.soft_delete(doc)
        logger.info("Document soft-deleted: patient=%s, doc=%s", patient_id, document_id)