from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status

from app.config import settings
from app.domain.models.schemas import (
    AppointmentCancelRequest, AppointmentCreate,
    AppointmentListResponse, AppointmentResponse,
    ExamRequestCreate, ExamRequestHistoryResponse, ExamRequestResponse, ExamResultUpdate,
    MedicalRecordCreate, MedicalRecordHistoryResponse, MedicalRecordResponse, MedicalRecordUpdate,
    PrescriptionCreate, PrescriptionHistoryResponse, PrescriptionPdfDownloadResponse, PrescriptionResponse,
    ScheduleCreate, ScheduleResponse,
    TimeSlotCreate, TimeSlotResponse,
)
from app.domain.services.clinical_service import (
    AppointmentService, ExamRequestService,
    MedicalRecordService, PrescriptionService,
)
from shared.metrics import (
    consultations_total, prescriptions_total, medical_records_total, exam_requests_total,
)
from shared.middleware.auth import make_auth_dependency
from app.config import settings as _settings

get_current_user, require_roles = make_auth_dependency(
    settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM
)

appointments_router = APIRouter(prefix="/appointments", tags=["Appointments"])
schedules_router = APIRouter(prefix="/schedules", tags=["Schedules"])
records_router = APIRouter(prefix="/records", tags=["Medical Records"])


def _sf(r: Request):
    return r.app.state.session_factory

def _pub(r: Request):
    return r.app.state.publisher


# ─── Appointments ─────────────────────────────────────────────────────────────

@appointments_router.get("", response_model=AppointmentListResponse)
async def list_appointments(
    request: Request,
    user=Depends(get_current_user),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    patient_id: Optional[str] = Query(None),
    doctor_id: Optional[str] = Query(None),
    appt_status: Optional[str] = Query(None, alias="status"),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
):
    # Restrict patients to their own appointments
    if user.role == "PATIENT":
        patient_id = user.sub
    if user.role == "DOCTOR":
        doctor_id = user.sub

    async with _sf(request)() as session:
        svc = AppointmentService(session, _pub(request))
        items, total = await svc.list_appointments(page, size, patient_id, doctor_id, appt_status, from_date, to_date)
        return AppointmentListResponse(
            items=[AppointmentResponse.model_validate(a) for a in items],
            total=total, page=page, size=size,
        )


@appointments_router.post(
    "",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("ADMIN", "ATTENDANT", "PATIENT"))],
)
async def create_appointment(body: AppointmentCreate, request: Request, user=Depends(get_current_user)):
    # Auto-atribuir patient_id para pacientes logados
    if user.role == "PATIENT":
        body.patient_id = user.sub
    if not body.patient_id:
        from fastapi import HTTPException as _HTTPException
        from fastapi import status as _status
        raise _HTTPException(
            status_code=_status.HTTP_400_BAD_REQUEST,
            detail="patient_id é obrigatório para não-pacientes",
        )
    async with _sf(request)() as session:
        svc = AppointmentService(session, _pub(request))
        result = await svc.create(body, user.sub)
        consultations_total.labels(service=_settings.SERVICE_NAME, status="scheduled").inc()
        return AppointmentResponse.model_validate(result)


@appointments_router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(appointment_id: str, request: Request, user=Depends(get_current_user)):
    async with _sf(request)() as session:
        svc = AppointmentService(session, _pub(request))
        return AppointmentResponse.model_validate(await svc.get(appointment_id))


@appointments_router.put("/{appointment_id}/cancel", response_model=AppointmentResponse)
async def cancel_appointment(
    appointment_id: str,
    body: AppointmentCancelRequest,
    request: Request,
    user=Depends(get_current_user),
):
    async with _sf(request)() as session:
        svc = AppointmentService(session, _pub(request))
        result = await svc.cancel(appointment_id, body, user.sub, user.role)
        consultations_total.labels(service=_settings.SERVICE_NAME, status="cancelled").inc()
        return AppointmentResponse.model_validate(result)


@appointments_router.put(
    "/{appointment_id}/confirm",
    response_model=AppointmentResponse,
    dependencies=[Depends(require_roles("DOCTOR", "ADMIN", "ATTENDANT"))],
)
async def confirm_appointment(appointment_id: str, request: Request, user=Depends(get_current_user)):
    async with _sf(request)() as session:
        svc = AppointmentService(session, _pub(request))
        result = await svc.confirm(appointment_id)
        consultations_total.labels(service=_settings.SERVICE_NAME, status="confirmed").inc()
        return AppointmentResponse.model_validate(result)


@appointments_router.put(
    "/{appointment_id}/complete",
    response_model=AppointmentResponse,
    dependencies=[Depends(require_roles("DOCTOR", "ADMIN"))],
)
async def complete_appointment(appointment_id: str, request: Request, user=Depends(get_current_user)):
    async with _sf(request)() as session:
        svc = AppointmentService(session, _pub(request))
        result = await svc.complete(appointment_id)
        consultations_total.labels(service=_settings.SERVICE_NAME, status="completed").inc()
        return AppointmentResponse.model_validate(result)


# ─── Medical Records ──────────────────────────────────────────────────────────

@records_router.post(
    "",
    response_model=MedicalRecordResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("DOCTOR"))],
)
async def create_record(body: MedicalRecordCreate, request: Request, user=Depends(get_current_user)):
    async with _sf(request)() as session:
        svc = MedicalRecordService(session, _pub(request))
        record = await svc.create(body, user.sub)
        medical_records_total.labels(service=_settings.SERVICE_NAME).inc()
        record = await svc.repo.get(record.id, load_relations=True)
        return MedicalRecordResponse.model_validate(record)


@records_router.get("/{record_id}", response_model=MedicalRecordResponse)
async def get_record(record_id: str, request: Request, user=Depends(get_current_user)):
    async with _sf(request)() as session:
        svc = MedicalRecordService(session, _pub(request))
        return MedicalRecordResponse.model_validate(await svc.get(record_id, user.sub, user.role))


@records_router.put(
    "/{record_id}",
    response_model=MedicalRecordResponse,
    dependencies=[Depends(require_roles("DOCTOR"))],
)
async def update_record(record_id: str, body: MedicalRecordUpdate, request: Request, user=Depends(get_current_user)):
    async with _sf(request)() as session:
        svc = MedicalRecordService(session, _pub(request))
        record = await svc.update(record_id, body, user.sub)
        record = await svc.repo.get(record.id, load_relations=True)
        return MedicalRecordResponse.model_validate(record)


@records_router.post(
    "/{record_id}/sign",
    response_model=MedicalRecordResponse,
    dependencies=[Depends(require_roles("DOCTOR"))],
)
async def sign_record(record_id: str, request: Request, user=Depends(get_current_user)):
    """Digitally sign a medical record — computes and stores an integrity hash."""
    async with _sf(request)() as session:
        svc = MedicalRecordService(session, _pub(request))
        record = await svc.sign(record_id, user.sub)
        record = await svc.repo.get(record.id, load_relations=True)
        return MedicalRecordResponse.model_validate(record)


@records_router.get(
    "/{record_id}/signature/verify",
    dependencies=[Depends(require_roles("DOCTOR", "ADMIN"))],
)
async def verify_record_signature(record_id: str, request: Request):
    """Verify the digital signature integrity of a medical record."""
    async with _sf(request)() as session:
        svc = MedicalRecordService(session, _pub(request))
        return await svc.verify_signature(record_id)


@records_router.get(
    "/{record_id}/history",
    response_model=list[MedicalRecordHistoryResponse],
    dependencies=[Depends(require_roles("DOCTOR", "ADMIN"))],
)
async def get_record_history(record_id: str, request: Request):
    """Get the full audit history of a medical record."""
    async with _sf(request)() as session:
        svc = MedicalRecordService(session, _pub(request))
        record = await svc.repo.get(record_id, load_relations=True)
        if not record:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Prontuário não encontrado")
        return [MedicalRecordHistoryResponse.model_validate(h) for h in record.history]


@records_router.get("/patient/{patient_id}", response_model=dict)
async def list_patient_records(
    patient_id: str, request: Request,
    user=Depends(require_roles("DOCTOR", "ADMIN")),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=50),
):
    async with _sf(request)() as session:
        svc = MedicalRecordService(session, _pub(request))
        items, total = await svc.list_by_patient(patient_id, page, size)
        return {
            "items": [MedicalRecordResponse.model_validate(r) for r in items],
            "total": total, "page": page, "size": size,
        }


# ─── Prescriptions ────────────────────────────────────────────────────────────

@records_router.post(
    "/{record_id}/prescriptions",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("DOCTOR"))],
)
async def create_prescription(record_id: str, body: PrescriptionCreate, request: Request, user=Depends(get_current_user)):
    async with _sf(request)() as session:
        svc = PrescriptionService(session, _pub(request))
        result = await svc.create(record_id, body, user.sub)
        prescriptions_total.labels(service=_settings.SERVICE_NAME).inc()
        return PrescriptionResponse.model_validate(result)


@records_router.get(
    "/{record_id}/prescriptions/{prescription_id}/pdf/download",
    response_model=PrescriptionPdfDownloadResponse,
    dependencies=[Depends(require_roles("DOCTOR", "ADMIN", "ATTENDANT"))],
)
async def download_prescription_pdf_url(record_id: str, prescription_id: str, request: Request):
    """Get a pre-signed S3 URL to download the prescription PDF."""
    async with _sf(request)() as session:
        svc = PrescriptionService(session, _pub(request))
        url = await svc.get_pdf_download_url(prescription_id)
        return PrescriptionPdfDownloadResponse(
            download_url=url,
            expires_in_seconds=settings.S3_PRESIGNED_URL_EXPIRY,
        )


@records_router.get(
    "/{record_id}/prescriptions/{prescription_id}/history",
    response_model=list[PrescriptionHistoryResponse],
    dependencies=[Depends(require_roles("DOCTOR", "ADMIN"))],
)
async def get_prescription_history(record_id: str, prescription_id: str, request: Request):
    """Get the audit history of a prescription."""
    from app.infrastructure.repositories.clinical_repository import PrescriptionRepository
    async with _sf(request)() as session:
        repo = PrescriptionRepository(session)
        rx = await repo.get(prescription_id)
        if not rx:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Prescrição não encontrada")
        from app.domain.models.clinical import PrescriptionHistory
        from sqlalchemy import select
        result = await session.execute(
            select(PrescriptionHistory)
            .where(PrescriptionHistory.prescription_id == prescription_id)
            .order_by(PrescriptionHistory.created_at.desc())
        )
        return [PrescriptionHistoryResponse.model_validate(h) for h in result.scalars().all()]


@records_router.get(
    "/{record_id}/prescriptions/{prescription_id}/pdf",
    summary="Download do PDF da prescrição",
)
async def download_prescription_pdf(
    record_id: str,
    prescription_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    import boto3 as _boto3
    from sqlalchemy import select
    from app.domain.models.clinical import Prescription as _Prescription
    from fastapi.responses import JSONResponse, RedirectResponse

    async with _sf(request)() as session:
        result = await session.execute(
            select(_Prescription).where(
                _Prescription.id == prescription_id,
                _Prescription.record_id == record_id,
            )
        )
        rx = result.scalar_one_or_none()

    if not rx:
        raise HTTPException(status_code=404, detail="Prescrição não encontrada")

    if not rx.pdf_s3_key:
        return JSONResponse(
            status_code=202,
            content={"detail": "PDF ainda está sendo gerado. Tente novamente em alguns segundos."},
        )

    s3 = _boto3.client(
        "s3",
        endpoint_url=_settings.S3_ENDPOINT,
        aws_access_key_id=_settings.S3_ACCESS_KEY,
        aws_secret_access_key=_settings.S3_SECRET_KEY,
    )
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": _settings.S3_BUCKET_PRESCRIPTIONS, "Key": rx.pdf_s3_key},
        ExpiresIn=300,
    )
    return RedirectResponse(url=url, status_code=302)


# ─── Exam Requests ────────────────────────────────────────────────────────────

@records_router.post(
    "/{record_id}/exams",
    response_model=ExamRequestResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("DOCTOR"))],
)
async def create_exam(record_id: str, body: ExamRequestCreate, request: Request, user=Depends(get_current_user)):
    async with _sf(request)() as session:
        svc = ExamRequestService(session)
        result = await svc.create(record_id, body, user.sub)
        exam_requests_total.labels(service=_settings.SERVICE_NAME, status="requested").inc()
        return ExamRequestResponse.model_validate(result)


@records_router.put(
    "/{record_id}/exams/{exam_id}/result",
    response_model=ExamRequestResponse,
    dependencies=[Depends(require_roles("DOCTOR", "ADMIN"))],
)
async def record_exam_result(
    record_id: str, exam_id: str, body: ExamResultUpdate,
    request: Request, user=Depends(get_current_user),
):
    async with _sf(request)() as session:
        svc = ExamRequestService(session)
        result = await svc.record_result(record_id, exam_id, body, user.sub)
        exam_requests_total.labels(service=_settings.SERVICE_NAME, status="completed").inc()
        return ExamRequestResponse.model_validate(result)


@records_router.get(
    "/{record_id}/exams/{exam_id}/history",
    response_model=list[ExamRequestHistoryResponse],
    dependencies=[Depends(require_roles("DOCTOR", "ADMIN"))],
)
async def get_exam_history(record_id: str, exam_id: str, request: Request):
    """Get the audit history of an exam request."""
    from app.domain.models.clinical import ExamRequestHistory
    from sqlalchemy import select
    async with _sf(request)() as session:
        result = await session.execute(
            select(ExamRequestHistory)
            .where(ExamRequestHistory.exam_id == exam_id)
            .order_by(ExamRequestHistory.created_at.desc())
        )
        return [ExamRequestHistoryResponse.model_validate(h) for h in result.scalars().all()]