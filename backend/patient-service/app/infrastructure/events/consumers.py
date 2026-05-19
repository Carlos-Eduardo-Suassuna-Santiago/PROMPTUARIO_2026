"""
Patient Service event consumer.
Listens to IAM events and reacts accordingly.
"""
from __future__ import annotations

import json
import logging

from shared.events import UserDeactivatedEvent
from shared.events.broker import EventConsumer

logger = logging.getLogger(__name__)


def setup_consumers(consumer: EventConsumer, session_factory, publisher) -> None:
    """Register all event handlers for Patient Service."""

    consumer.register(
        exchange=UserDeactivatedEvent.EXCHANGE,
        routing_key=UserDeactivatedEvent.ROUTING_KEY,
        handler=_make_user_deactivated_handler(session_factory, publisher),
    )


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
