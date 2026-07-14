from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from typing import Literal, Optional

from app.config import settings
from app.domain.services.ai_service import AIService
# from shared.audit import log_operation
from shared.events import MedicalRecordCreatedEvent, PrescriptionGeneratedEvent
from shared.events.broker import EventConsumer, EventPublisher
from shared.middleware.auth import make_auth_dependency
from shared.observability import setup_observability, get_request_context

logger = logging.getLogger(__name__)

get_current_user, require_roles = make_auth_dependency(
    settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM
)

# ─── Schemas ─────────────────────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    analysis_type: Literal["DRUG_INTERACTION_CHECK", "SYMPTOM_ANALYSIS", "CLINICAL_SUMMARY"]
    patient_id: str
    record_id: Optional[str] = None
    context: dict = {}


# ─── Router ──────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/ai", tags=["AI Analysis"])


@router.post(
    "/analyze",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_roles("DOCTOR", "ADMIN"))],
)
async def submit_analysis(body: AnalysisRequest, request: Request, user=Depends(get_current_user)):
    svc = AIService(request.app.state.db, request.app.state.redis)
    job = await svc.create_job(
        analysis_type=body.analysis_type,
        patient_id=body.patient_id,
        record_id=body.record_id,
        context=body.context,
    )
    # Run analysis asynchronously
    asyncio.create_task(
        svc.run_analysis(job["_id"], publisher=request.app.state.publisher)
    )
    # Audit the analysis request (disabled for MongoDB for now)
    ctx = get_request_context()
    # await log_operation(
    #     request.app.state.db.client,
    #     service="ai-service",
    #     table="analysis_jobs",
    #     operation="AI_ANALYSIS_REQUESTED",
    #     record_id=job["_id"],
    #     user_id=user.sub,
    #     user_role=user.role,
    #     new_values={
    #         "analysis_type": body.analysis_type,
    #         "patient_id": body.patient_id,
    #         "record_id": body.record_id,
    #     },
    #     request_id=ctx.get("request_id"),
    #     correlation_id=ctx.get("correlation_id"),
    # )
    return {"job_id": job["_id"], "status": "PENDING"}


@router.get("/jobs/{job_id}", dependencies=[Depends(require_roles("DOCTOR", "ADMIN"))])
async def get_job(job_id: str, request: Request):
    svc = AIService(request.app.state.db)
    job = await svc.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    job["id"] = job.pop("_id")
    return job


@router.get("/records/{record_id}/analyses", dependencies=[Depends(require_roles("DOCTOR", "ADMIN"))])
async def list_analyses(record_id: str, request: Request):
    svc = AIService(request.app.state.db)
    jobs = await svc.list_by_record(record_id)
    for j in jobs:
        j["id"] = j.pop("_id")
    return {"items": jobs, "total": len(jobs)}


# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="PROMPTUARIO — AI Service",
    description="Análise clínica com IA: interações medicamentosas, sintomas, resumos",
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

app.include_router(router, prefix="/api/v1")


@app.on_event("startup")
async def startup():
    # MongoDB via Motor
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    app.state.db = client.ai_db
    # Ensure indexes
    await app.state.db.analysis_jobs.create_index("patient_id")
    await app.state.db.analysis_jobs.create_index("record_id")
    await app.state.db.analysis_jobs.create_index("status")
    await app.state.db.analysis_jobs.create_index("created_at")

    # Redis
    import redis.asyncio as aioredis
    app.state.redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    # Publisher
    publisher = EventPublisher(settings.RABBITMQ_URL)
    await publisher.connect()
    app.state.publisher = publisher

    # Consumer — auto-analyze when MedicalRecord is created
    consumer = EventConsumer(settings.RABBITMQ_URL, settings.SERVICE_NAME)
    await consumer.connect()
    _setup_consumers(consumer, app.state.db, app.state.redis, publisher)
    await consumer.start()
    app.state.consumer = consumer

    logger.info("AI Service started ✅")


@app.on_event("shutdown")
async def shutdown():
    await app.state.publisher.close()
    await app.state.consumer.close()
    await app.state.redis.aclose()


def _setup_consumers(consumer: EventConsumer, db, redis_client, publisher):
    consumer.register(
        exchange=MedicalRecordCreatedEvent.EXCHANGE,
        routing_key=MedicalRecordCreatedEvent.ROUTING_KEY,
        handler=_make_record_created_handler(db, redis_client, publisher),
    )
    consumer.register(
        exchange=PrescriptionGeneratedEvent.EXCHANGE,
        routing_key=PrescriptionGeneratedEvent.ROUTING_KEY,
        handler=_make_prescription_handler(db, redis_client, publisher),
    )


def _make_record_created_handler(db, redis_client, publisher):
    async def handle(body: bytes) -> None:
        try:
            data = json.loads(body)
            svc = AIService(db, redis_client)
            job = await svc.create_job(
                analysis_type="SYMPTOM_ANALYSIS",
                patient_id=data["patient_id"],
                record_id=data["record_id"],
                context={
                    "chief_complaint": data.get("chief_complaint", ""),
                    "diagnosis_codes": data.get("diagnosis_codes", []),
                },
            )
            await svc.run_analysis(job["_id"], publisher=publisher)
            logger.info("Auto-analysis completed for record %s", data["record_id"])
        except Exception as e:
            logger.error("Error in auto-analysis: %s", e)
            raise
    return handle


def _make_prescription_handler(db, redis_client, publisher):
    async def handle(body: bytes) -> None:
        try:
            data = json.loads(body)
            svc = AIService(db, redis_client)
            job = await svc.create_job(
                analysis_type="DRUG_INTERACTION_CHECK",
                patient_id=data["patient_id"],
                record_id=data["record_id"],
                context={"medications": data.get("medications", [])},
            )
            await svc.run_analysis(job["_id"], publisher=publisher)
            logger.info("Drug interaction check completed for prescription %s", data["prescription_id"])
        except Exception as e:
            logger.error("Error in drug interaction check: %s", e)
            raise
    return handle


@app.get("/healthz", tags=["Health"])
async def health(request: Request):
    circuit_state = "N/A"
    llm_metrics = {}
    try:
        svc = AIService(request.app.state.db)
        client = svc._get_llm_client()
        circuit_state = client.state
        llm_metrics = client.metrics
    except Exception:
        pass
    return {
        "status": "ok",
        "service": settings.SERVICE_NAME,
        "llm_configured": bool(settings.LLM_API_KEY),
        "llm_model": settings.LLM_MODEL,
        "circuit_breaker": circuit_state,
        "llm_metrics": llm_metrics,
    }