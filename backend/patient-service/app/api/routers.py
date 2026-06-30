from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status

from app.config import settings
from app.domain.models.schemas import (
    AllergyCreate, AllergyResponse,
    MedicationCreate, MedicationResponse,
    PatientCreate, PatientListResponse, PatientResponse, PatientSummaryResponse, PatientUpdate,
    VaccineCreate, VaccineResponse,
)
from app.domain.services.patient_service import (
    AllergyService, MedicationService, PatientService, VaccineService,
)
from shared.metrics import (
    patients_registered_total, patients_active_total,
    allergies_registered_total, vaccines_registered_total,
)
from shared.middleware.auth import make_auth_dependency
from app.config import settings as _settings

get_current_user, require_roles = make_auth_dependency(
    settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM
)

router = APIRouter(prefix="/patients", tags=["Patients"])


def _sf(request: Request):
    return request.app.state.session_factory


def _pub(request: Request):
    return request.app.state.publisher


# ─── Patients ─────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=PatientListResponse,
    dependencies=[Depends(require_roles("ADMIN", "DOCTOR", "ATTENDANT"))],
)
async def list_patients(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
):
    async with _sf(request)() as session:
        svc = PatientService(session, _pub(request))
        items, total = await svc.list_patients(page, size, search)
        return PatientListResponse(
            items=[PatientResponse.model_validate(p) for p in items],
            total=total, page=page, size=size,
        )


@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("ADMIN", "ATTENDANT"))],
)
async def create_patient(body: PatientCreate, request: Request):
    async with _sf(request)() as session:
        svc = PatientService(session, _pub(request))
        patient = await svc.create(body)
        patients_registered_total.labels(service=_settings.SERVICE_NAME).inc()
        patients_active_total.labels(service=_settings.SERVICE_NAME).inc()
        return PatientResponse.model_validate(patient)


@router.get("/me", response_model=PatientResponse)
async def get_my_patient(request: Request, user=Depends(get_current_user)):
    async with _sf(request)() as session:
        svc = PatientService(session, _pub(request))
        return PatientResponse.model_validate(await svc.get_by_user(user.sub))


@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
    dependencies=[Depends(require_roles("ADMIN", "DOCTOR", "ATTENDANT"))],
)
async def get_patient(patient_id: str, request: Request):
    async with _sf(request)() as session:
        svc = PatientService(session, _pub(request))
        return PatientResponse.model_validate(await svc.get(patient_id))


@router.get("/{patient_id}/summary", response_model=PatientSummaryResponse)
async def get_patient_summary(
    patient_id: str,
    request: Request,
    user=Depends(require_roles("ADMIN", "DOCTOR", "ATTENDANT")),
):
    async with _sf(request)() as session:
        svc = PatientService(session, _pub(request))
        return PatientSummaryResponse.model_validate(await svc.get_summary(patient_id))


@router.put("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: str, body: PatientUpdate, request: Request,
    user=Depends(get_current_user),
):
    async with _sf(request)() as session:
        svc = PatientService(session, _pub(request))
        return PatientResponse.model_validate(
            await svc.update(patient_id, body, user.sub, user.role)
        )


@router.delete(
    "/{patient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def deactivate_patient(patient_id: str, request: Request):
    async with _sf(request)() as session:
        svc = PatientService(session, _pub(request))
        await svc.deactivate(patient_id)
        patients_active_total.labels(service=_settings.SERVICE_NAME).dec()


# ─── Allergies ────────────────────────────────────────────────────────────────

@router.get(
    "/{patient_id}/allergies",
    response_model=list[AllergyResponse],
    dependencies=[Depends(require_roles("ADMIN", "DOCTOR", "ATTENDANT"))],
)
async def list_allergies(patient_id: str, request: Request):
    async with _sf(request)() as session:
        svc = AllergyService(session, _pub(request))
        return [AllergyResponse.model_validate(a) for a in await svc.list(patient_id)]


@router.post(
    "/{patient_id}/allergies",
    response_model=AllergyResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("ADMIN", "DOCTOR", "ATTENDANT"))],
)
async def create_allergy(patient_id: str, body: AllergyCreate, request: Request):
    async with _sf(request)() as session:
        svc = AllergyService(session, _pub(request))
        allergy = await svc.create(patient_id, body)
        allergies_registered_total.labels(service=_settings.SERVICE_NAME).inc()
        return AllergyResponse.model_validate(allergy)


@router.delete(
    "/{patient_id}/allergies/{allergy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles("ADMIN", "DOCTOR"))],
)
async def delete_allergy(patient_id: str, allergy_id: str, request: Request):
    async with _sf(request)() as session:
        svc = AllergyService(session, _pub(request))
        await svc.delete(patient_id, allergy_id)


# ─── Vaccines ─────────────────────────────────────────────────────────────────

@router.get(
    "/{patient_id}/vaccines",
    response_model=list[VaccineResponse],
    dependencies=[Depends(require_roles("ADMIN", "DOCTOR", "ATTENDANT"))],
)
async def list_vaccines(patient_id: str, request: Request):
    async with _sf(request)() as session:
        svc = VaccineService(session, _pub(request))
        return [VaccineResponse.model_validate(v) for v in await svc.list(patient_id)]


@router.post(
    "/{patient_id}/vaccines",
    response_model=VaccineResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("ADMIN", "DOCTOR", "ATTENDANT"))],
)
async def create_vaccine(patient_id: str, body: VaccineCreate, request: Request):
    async with _sf(request)() as session:
        svc = VaccineService(session, _pub(request))
        vaccine = await svc.create(patient_id, body)
        vaccines_registered_total.labels(service=_settings.SERVICE_NAME).inc()
        return VaccineResponse.model_validate(vaccine)


@router.delete(
    "/{patient_id}/vaccines/{vaccine_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles("ADMIN", "DOCTOR"))],
)
async def delete_vaccine(patient_id: str, vaccine_id: str, request: Request):
    async with _sf(request)() as session:
        svc = VaccineService(session, _pub(request))
        await svc.delete(patient_id, vaccine_id)


# ─── Medications ──────────────────────────────────────────────────────────────

@router.get(
    "/{patient_id}/medications",
    response_model=list[MedicationResponse],
    dependencies=[Depends(require_roles("ADMIN", "DOCTOR", "ATTENDANT"))],
)
async def list_medications(
    patient_id: str,
    request: Request,
    active_only: bool = Query(False),
):
    async with _sf(request)() as session:
        svc = MedicationService(session, _pub(request))
        return [MedicationResponse.model_validate(m) for m in await svc.list(patient_id, active_only)]


@router.post(
    "/{patient_id}/medications",
    response_model=MedicationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("ADMIN", "DOCTOR", "ATTENDANT"))],
)
async def create_medication(patient_id: str, body: MedicationCreate, request: Request):
    async with _sf(request)() as session:
        svc = MedicationService(session, _pub(request))
        return MedicationResponse.model_validate(await svc.create(patient_id, body))


@router.delete(
    "/{patient_id}/medications/{med_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles("ADMIN", "DOCTOR"))],
)
async def delete_medication(patient_id: str, med_id: str, request: Request):
    async with _sf(request)() as session:
        svc = MedicationService(session, _pub(request))
        await svc.deactivate(patient_id, med_id)
