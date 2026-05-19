from __future__ import annotations

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import router
from app.config import settings
from app.domain.models.patient import Allergy, ContinuousMedication, Patient, Vaccine
from app.infrastructure.events.consumers import setup_consumers
from shared.events.broker import EventConsumer, EventPublisher
from shared.models.database import Base, build_engine, build_session_factory

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PROMPTUARIO — Patient Service",
    description="Cadastro e histórico de saúde de pacientes",
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

    publisher = EventPublisher(settings.RABBITMQ_URL)
    await publisher.connect()
    app.state.publisher = publisher

    consumer = EventConsumer(settings.RABBITMQ_URL, settings.SERVICE_NAME)
    await consumer.connect()
    setup_consumers(consumer, app.state.session_factory, publisher)
    await consumer.start()
    app.state.consumer = consumer

    logger.info("Patient Service started ✅")


@app.on_event("shutdown")
async def shutdown():
    await app.state.publisher.close()
    await app.state.consumer.close()


@app.get("/healthz", tags=["Health"])
async def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}
