from __future__ import annotations

import logging

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers import auth_router, users_router
from app.config import settings
from app.domain.models.user import User
from shared.events.broker import EventPublisher
from shared.models.database import Base, build_engine, build_session_factory
from shared.observability import setup_observability
from shared.utils.security import hash_password

logger = logging.getLogger(__name__)

app = FastAPI(
    title="PROMPTUARIO — IAM Service",
    description="Identity & Access Management: autenticação, usuários e roles",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_observability(app, settings.SERVICE_NAME, settings.LOG_LEVEL)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")


@app.on_event("startup")
async def startup():
    # Database
    engine = build_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.state.session_factory = build_session_factory(engine)

    # Redis
    app.state.redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    # RabbitMQ publisher
    publisher = EventPublisher(settings.RABBITMQ_URL)
    await publisher.connect()
    app.state.publisher = publisher

    # Seed first admin
    await _seed_admin()
    logger.info("IAM Service started ✅")


@app.on_event("shutdown")
async def shutdown():
    await app.state.publisher.close()
    await app.state.redis.aclose()


async def _seed_admin():
    """Create the first ADMIN user if none exists."""
    from app.infrastructure.repositories.user_repository import UserRepository
    import uuid

    async with app.state.session_factory() as session:
        repo = UserRepository(session)
        existing = await repo.get_by_email(settings.FIRST_ADMIN_EMAIL)
        if existing:
            existing.hashed_password = hash_password(settings.FIRST_ADMIN_PASSWORD)
            existing.full_name = settings.FIRST_ADMIN_NAME
            existing.role = "ADMIN"
            existing.is_active = True
            existing.deactivated_at = None
            existing.deactivation_reason = None
            await repo.update(existing)
            logger.info("Admin seed sincronizado: %s", settings.FIRST_ADMIN_EMAIL)
        else:
            admin = User(
                id=str(uuid.uuid4()),
                email=settings.FIRST_ADMIN_EMAIL,
                hashed_password=hash_password(settings.FIRST_ADMIN_PASSWORD),
                full_name=settings.FIRST_ADMIN_NAME,
                role="ADMIN",
            )
            await repo.create(admin)
            logger.info("Admin seed criado: %s", settings.FIRST_ADMIN_EMAIL)
        await session.commit()


@app.get("/healthz", tags=["Health"])
async def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}
