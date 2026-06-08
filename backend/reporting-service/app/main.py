from __future__ import annotations

import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import func, select, text

from app.config import settings
from app.domain.models.report import DailyStats, ReportJob
from app.workers.celery_tasks import celery_app
from shared.events import (
    AppointmentCancelledEvent,
    AppointmentCreatedEvent,
    MedicalRecordCreatedEvent,
    PatientCreatedEvent,
    PrescriptionGeneratedEvent,
)
from shared.events.broker import EventConsumer, EventPublisher
from shared.middleware.auth import make_auth_dependency
from shared.models.database import Base, build_engine, build_session_factory

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

get_current_user, require_roles = make_auth_dependency(
    settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM
)

# ─── Schemas ─────────────────────────────────────────────────────────────────

class ReportRequest(BaseModel):
    report_type: Literal["CONSULTATIONS", "PATIENTS", "DOCTORS", "PRESCRIPTIONS"]
    output_format: Literal["JSON", "CSV", "PDF"] = "JSON"
    parameters: dict = {}


class ReportJobResponse(BaseModel):
    id: str
    report_type: str
    status: str
    output_format: str
    row_count: int
    s3_key: Optional[str] = None
    result_data: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


# ─── Router ──────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/reports", tags=["Reports"])


def _sf(r: Request):
    return r.app.state.session_factory


@router.post(
    "/export",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_roles("ADMIN", "DOCTOR"))],
)
async def request_report(body: ReportRequest, request: Request, user=Depends(get_current_user)):
    async with _sf(request)() as session:
        job = ReportJob(
            id=str(uuid.uuid4()),
            report_type=body.report_type,
            output_format=body.output_format,
            parameters=body.parameters,
            requested_by=user.sub,
        )
        session.add(job)
        await session.commit()

    # Dispatch to Celery worker
    celery_app.send_task("reporting.generate_report", args=[job.id])
    return {"job_id": job.id, "status": "PENDING"}


@router.get(
    "/export/{job_id}",
    response_model=ReportJobResponse,
    dependencies=[Depends(require_roles("ADMIN", "DOCTOR"))],
)
async def get_report_job(job_id: str, request: Request):
    async with _sf(request)() as session:
        result = await session.execute(select(ReportJob).where(ReportJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job não encontrado")
        return ReportJobResponse.model_validate(job)


@router.get(
    "/export/{job_id}/download",
    dependencies=[Depends(require_roles("ADMIN", "DOCTOR"))],
)
async def download_report(job_id: str, request: Request):
    async with _sf(request)() as session:
        result = await session.execute(select(ReportJob).where(ReportJob.id == job_id))
        job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if job.status != "COMPLETED":
        raise HTTPException(status_code=400, detail=f"Relatório ainda não concluído: {job.status}")
    if not job.s3_key:
        raise HTTPException(status_code=400, detail="Arquivo não disponível (JSON output)")

    # Generate pre-signed URL
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_REPORTS, "Key": job.s3_key},
        ExpiresIn=300,  # 5 minutes
    )
    return RedirectResponse(url=url, status_code=302)


@router.get(
    "/consultations",
    dependencies=[Depends(require_roles("ADMIN", "DOCTOR"))],
)
async def consultations_report(
    request: Request,
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
):
    async with _sf(request)() as session:
        q = select(DailyStats).where(DailyStats.stat_type == "CONSULTATIONS")
        if from_date:
            q = q.where(DailyStats.stat_date >= from_date)
        if to_date:
            q = q.where(DailyStats.stat_date <= to_date)
        result = await session.execute(q.order_by(DailyStats.stat_date.desc()).limit(90))
        rows = result.scalars().all()
        return {
            "data": [{"date": r.stat_date, "consultations": r.value} for r in rows],
            "total_days": len(rows),
        }


@router.get(
    "/patients",
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def patients_report(
    request: Request,
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
):
    async with _sf(request)() as session:
        q = select(DailyStats).where(DailyStats.stat_type == "NEW_PATIENTS")
        if from_date:
            q = q.where(DailyStats.stat_date >= from_date)
        if to_date:
            q = q.where(DailyStats.stat_date <= to_date)
        result = await session.execute(q.order_by(DailyStats.stat_date.desc()).limit(90))
        rows = result.scalars().all()
        total = sum(r.value for r in rows)
        return {
            "data": [{"date": r.stat_date, "new_patients": r.value} for r in rows],
            "total_new_patients": total,
        }


@router.get(
    "/doctors",
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def doctors_report(
    request: Request,
    doctor_id: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
):
    async with _sf(request)() as session:
        q = select(DailyStats).where(DailyStats.stat_type == "DOCTOR_CONSULTATIONS")
        if doctor_id:
            q = q.where(DailyStats.entity_id == doctor_id)
        if from_date:
            q = q.where(DailyStats.stat_date >= from_date)
        if to_date:
            q = q.where(DailyStats.stat_date <= to_date)
        result = await session.execute(q.order_by(DailyStats.stat_date.desc()).limit(200))
        rows = result.scalars().all()
        return {
            "data": [
                {"doctor_id": r.entity_id, "date": r.stat_date, "consultations": r.value}
                for r in rows
            ],
        }


@router.get(
    "/summary",
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def dashboard_summary(request: Request):
    """Quick dashboard numbers for the admin panel."""
    async with _sf(request)() as session:
        today = datetime.now(timezone.utc).date().isoformat()

        consultations_today = await session.scalar(
            select(func.sum(DailyStats.value)).where(
                DailyStats.stat_type == "CONSULTATIONS",
                DailyStats.stat_date == today,
            )
        ) or 0

        new_patients_month = await session.scalar(
            select(func.sum(DailyStats.value)).where(
                DailyStats.stat_type == "NEW_PATIENTS",
                DailyStats.stat_date >= today[:7] + "-01",
            )
        ) or 0

        cancellations_today = await session.scalar(
            select(func.sum(DailyStats.value)).where(
                DailyStats.stat_type == "CANCELLATIONS",
                DailyStats.stat_date == today,
            )
        ) or 0

        return {
            "consultations_today": consultations_today,
            "new_patients_this_month": new_patients_month,
            "cancellations_today": cancellations_today,
            "as_of": datetime.now(timezone.utc).isoformat(),
        }


# ─── Event Consumers — update DailyStats ─────────────────────────────────────

def _setup_consumers(consumer: EventConsumer, session_factory) -> None:
    consumer.register(
        exchange=AppointmentCreatedEvent.EXCHANGE,
        routing_key=AppointmentCreatedEvent.ROUTING_KEY,
        handler=_make_stat_handler(session_factory, "CONSULTATIONS", "appointment_id"),
    )
    consumer.register(
        exchange=AppointmentCancelledEvent.EXCHANGE,
        routing_key=AppointmentCancelledEvent.ROUTING_KEY,
        handler=_make_stat_handler(session_factory, "CANCELLATIONS", "appointment_id"),
    )
    consumer.register(
        exchange=PatientCreatedEvent.EXCHANGE,
        routing_key=PatientCreatedEvent.ROUTING_KEY,
        handler=_make_stat_handler(session_factory, "NEW_PATIENTS", "patient_id"),
    )
    consumer.register(
        exchange=MedicalRecordCreatedEvent.EXCHANGE,
        routing_key=MedicalRecordCreatedEvent.ROUTING_KEY,
        handler=_make_doctor_stat_handler(session_factory),
    )


def _make_stat_handler(session_factory, stat_type: str, id_field: str):
    async def handle(body: bytes) -> None:
        try:
            data = json.loads(body)
            today = datetime.now(timezone.utc).date().isoformat()
            async with session_factory() as session:
                # Upsert: increment stat for today
                existing = await session.execute(
                    select(DailyStats).where(
                        DailyStats.stat_type == stat_type,
                        DailyStats.stat_date == today,
                        DailyStats.entity_id == None,
                    )
                )
                row = existing.scalar_one_or_none()
                if row:
                    row.value += 1
                else:
                    session.add(DailyStats(
                        id=str(uuid.uuid4()),
                        stat_date=today,
                        stat_type=stat_type,
                        value=1,
                    ))
                await session.commit()
                logger.debug("Incremented %s for %s", stat_type, today)
        except Exception as e:
            logger.error("Error updating stat %s: %s", stat_type, e)
            raise
    return handle


def _make_doctor_stat_handler(session_factory):
    async def handle(body: bytes) -> None:
        try:
            data = json.loads(body)
            doctor_id = data.get("doctor_id")
            if not doctor_id:
                return
            today = datetime.now(timezone.utc).date().isoformat()
            async with session_factory() as session:
                existing = await session.execute(
                    select(DailyStats).where(
                        DailyStats.stat_type == "DOCTOR_CONSULTATIONS",
                        DailyStats.stat_date == today,
                        DailyStats.entity_id == doctor_id,
                    )
                )
                row = existing.scalar_one_or_none()
                if row:
                    row.value += 1
                else:
                    session.add(DailyStats(
                        id=str(uuid.uuid4()),
                        stat_date=today,
                        stat_type="DOCTOR_CONSULTATIONS",
                        entity_id=doctor_id,
                        value=1,
                    ))
                await session.commit()
        except Exception as e:
            logger.error("Error updating doctor stat: %s", e)
            raise
    return handle


# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="PROMPTUARIO — Reporting Service",
    description="Relatórios e exportações assíncronas via Celery + S3",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.on_event("startup")
async def startup():
    engine = build_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.state.session_factory = build_session_factory(engine)

    # Ensure S3 bucket exists
    _ensure_s3_bucket()

    publisher = EventPublisher(settings.RABBITMQ_URL)
    await publisher.connect()
    app.state.publisher = publisher

    consumer = EventConsumer(settings.RABBITMQ_URL, settings.SERVICE_NAME)
    await consumer.connect()
    _setup_consumers(consumer, app.state.session_factory)
    await consumer.start()
    app.state.consumer = consumer

    logger.info("Reporting Service started ✅")


@app.on_event("shutdown")
async def shutdown():
    await app.state.publisher.close()
    await app.state.consumer.close()


def _ensure_s3_bucket():
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
        )
        try:
            s3.head_bucket(Bucket=settings.S3_BUCKET_REPORTS)
        except ClientError:
            s3.create_bucket(Bucket=settings.S3_BUCKET_REPORTS)
            logger.info("S3 bucket created: %s", settings.S3_BUCKET_REPORTS)
    except Exception as e:
        logger.warning("Could not ensure S3 bucket (will retry): %s", e)


@app.get("/healthz", tags=["Health"])
async def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}
