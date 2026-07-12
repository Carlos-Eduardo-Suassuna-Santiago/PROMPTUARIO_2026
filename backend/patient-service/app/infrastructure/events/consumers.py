"""
Patient Service event consumer.
Listens to IAM events and reacts accordingly.
"""
from __future__ import annotations

import json
import logging

from shared.events import UserCreatedEvent, UserDeactivatedEvent
from shared.events.broker import EventConsumer

logger = logging.getLogger(__name__)


def setup_consumers(consumer: EventConsumer, session_factory, publisher) -> None:
    """Register all event handlers for Patient Service."""

    consumer.register(
        exchange=UserDeactivatedEvent.EXCHANGE,
        routing_key=UserDeactivatedEvent.ROUTING_KEY,
        handler=_make_user_deactivated_handler(session_factory, publisher),
    )

    consumer.register(
        exchange=UserCreatedEvent.EXCHANGE,
        routing_key=UserCreatedEvent.ROUTING_KEY,
        handler=_make_user_created_handler(session_factory, publisher),
    )


def _make_user_created_handler(session_factory, publisher):
    async def handle(body: bytes) -> None:
        try:
            data = json.loads(body)
            role = data.get("role")
            if role != "PATIENT":
                return

            user_id = data.get("user_id")
            if not user_id:
                return

            from app.domain.models.schemas import PatientCreate
            from app.domain.services.patient_service import PatientService

            async with session_factory() as session:
                svc = PatientService(session, publisher)
                
                # Check if patient already exists (idempotency)
                try:
                    await svc.get_by_user(user_id)
                    logger.info("Patient already exists for user %s", user_id)
                    return
                except Exception:
                    pass
                
                patient_create = PatientCreate(
                    user_id=user_id,
                    full_name=data.get("full_name"),
                    cpf=data.get("cpf"),
                    date_of_birth=data.get("date_of_birth"),
                    gender=data.get("gender"),
                    phone=data.get("phone"),
                    email=data.get("email"),
                )
                await svc.create(patient_create)
                await session.commit()
                logger.info("Patient profile created for user %s", user_id)

        except Exception as e:
            logger.error("Error handling UserCreated: %s", e)
            raise

    return handle


def _make_user_deactivated_handler(session_factory, publisher):
    async def handle(body: bytes) -> None:
        try:
            data = json.loads(body)
            user_id = data.get("user_id")
            if not user_id:
                return

            from app.infrastructure.repositories.patient_repository import PatientRepository
            from app.domain.services.patient_service import PatientService

            async with session_factory() as session:
                repo = PatientRepository(session)
                patient = await repo.get_by_user_id(user_id)
                if patient:
                    svc = PatientService(session, publisher)
                    await svc.deactivate(patient.id)
                    await session.commit()
                    logger.info("Patient deactivated for user %s", user_id)

        except Exception as e:
            logger.error("Error handling UserDeactivated: %s", e)
            raise

    return handle
