from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status

from app.config import settings
from app.domain.models.schemas import (
    AppointmentCancelRequest, AppointmentCreate,
    AppointmentListResponse, AppointmentResponse,
    ExamRequestCreate, ExamRequestResponse, ExamResultUpdate,
    MedicalRecordCreate, MedicalRecordResponse, MedicalRecordUpdate,
    PrescriptionCreate, PrescriptionResponse,
    ScheduleCreate, ScheduleResponse,
    TimeSlotCreate, TimeSlotResponse,
)
from app.domain.services.clinical_service import (
    AppointmentService, ExamRequestService,
    MedicalRecordService, PrescriptionService,
)
from shared.middleware.auth import make_auth_dependency

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
    async with _sf(request)() as session:
        svc = AppointmentService(session, _pub(request))
        return AppointmentResponse.model_validate(await svc.create(body, user.sub))


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
        return AppointmentResponse.model_validate(
            await svc.cancel(appointment_id, body, user.sub, user.role)
        )


@appointments_router.put(
    "/{appointment_id}/complete",
    response_model=AppointmentResponse,
    dependencies=[Depends(require_roles("DOCTOR", "ADMIN"))],
)
async def complete_appointment(appointment_id: str, request: Request, user=Depends(get_current_user)):
    async with _sf(request)() as session:
        svc = AppointmentService(session, _pub(request))
        return AppointmentResponse.model_validate(await svc.complete(appointment_id))


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
        return PrescriptionResponse.model_validate(await svc.create(record_id, body, user.sub))


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
        return ExamRequestResponse.model_validate(await svc.create(record_id, body, user.sub))


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
        return ExamRequestResponse.model_validate(
            await svc.record_result(record_id, exam_id, body, user.sub)
        )
