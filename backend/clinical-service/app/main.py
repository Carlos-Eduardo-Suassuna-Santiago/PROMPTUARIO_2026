from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import appointments_router, records_router, schedules_router
from app.config import settings
from app.domain.models.clinical import (
    Appointment, DoctorSchedule, ExamRequest, ExamRequestHistory,
    MedicalRecord, MedicalRecordHistory, PatientProjection,
    Prescription, PrescriptionHistory, TimeSlot,
)
from app.domain.services.clinical_service import _ensure_s3_bucket
from app.infrastructure.events.consumers import setup_consumers
from shared.events.broker import EventConsumer, EventPublisher
from shared.models.database import Base, build_engine, build_session_factory
from shared.observability import setup_observability

logger = logging.getLogger(__name__)

app = FastAPI(
    title="PROMPTUARIO — Clinical Service",
    description="Agendamentos, prontuários, prescrições e solicitações de exame",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_observability(app, settings.SERVICE_NAME, settings.LOG_LEVEL)

app.include_router(appointments_router, prefix="/api/v1")
app.include_router(records_router, prefix="/api/v1")
app.include_router(schedules_router, prefix="/api/v1")


@app.on_event("startup")
async def startup():
    engine = build_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.state.session_factory = build_session_factory(engine)

    publisher = EventPublisher(settings.RABBITMQ_URL)
    await publisher.connect()
    app.state.publisher = publisher

    consumer = EventConsumer(settings.RABBITMQ_URL, settings.SERVICE_NAME)
    await consumer.connect()
    setup_consumers(consumer, app.state.session_factory, publisher)
    await consumer.start()
    app.state.consumer = consumer

    # Ensure MinIO/S3 bucket exists for prescription PDFs
    _ensure_s3_bucket()

    logger.info("Clinical Service started ✅")


@app.on_event("shutdown")
async def shutdown():
    await app.state.publisher.close()
    await app.state.consumer.close()


@app.get("/healthz", tags=["Health"])
async def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}