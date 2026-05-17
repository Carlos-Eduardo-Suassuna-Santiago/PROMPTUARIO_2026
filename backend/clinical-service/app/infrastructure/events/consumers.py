from __future__ import annotations

import json
import logging
from datetime import date

from shared.events import PatientCreatedEvent, PatientUpdatedEvent, UserDeactivatedEvent
from shared.events.broker import EventConsumer

logger = logging.getLogger(__name__)


def setup_consumers(consumer: EventConsumer, session_factory, publisher) -> None:
    consumer.register(
        exchange=PatientCreatedEvent.EXCHANGE,
        routing_key=PatientCreatedEvent.ROUTING_KEY,
        handler=_make_patient_created_handler(session_factory),
    )
    consumer.register(
        exchange=PatientUpdatedEvent.EXCHANGE,
        routing_key=PatientUpdatedEvent.ROUTING_KEY,
        handler=_make_patient_updated_handler(session_factory),
    )
    consumer.register(
        exchange=UserDeactivatedEvent.EXCHANGE,
        routing_key=UserDeactivatedEvent.ROUTING_KEY,
        handler=_make_user_deactivated_handler(session_factory, publisher),
    )


def _make_patient_created_handler(session_factory):
    async def handle(body: bytes) -> None:
        try:
            data = json.loads(body)
            from app.domain.models.clinical import PatientProjection
            from app.infrastructure.repositories.clinical_repository import PatientProjectionRepository

            dob_str = data.get("date_of_birth")
            dob = date.fromisoformat(dob_str) if dob_str else None

            projection = PatientProjection(
                id=data["patient_id"],
                user_id=data["user_id"],
                full_name=data.get("full_name", ""),
                date_of_birth=dob,
                blood_type=data.get("blood_type"),
            )
            async with session_factory() as session:
                repo = PatientProjectionRepository(session)
                await repo.upsert(projection)
                await session.commit()
                logger.info("Patient projection created: %s", data["patient_id"])
        except Exception as e:
            logger.error("Error handling PatientCreated: %s", e)
            raise

    return handle


def _make_patient_updated_handler(session_factory):
    async def handle(body: bytes) -> None:
        try:
            data = json.loads(body)
            from app.domain.models.clinical import PatientProjection
            from app.infrastructure.repositories.clinical_repository import PatientProjectionRepository

            async with session_factory() as session:
                repo = PatientProjectionRepository(session)
                projection = await session.get(PatientProjection, data["patient_id"])
                if projection:
                    if "phone" in data.get("changed_fields", []):
                        projection.phone = data.get("phone")
                    await session.commit()
                    logger.info("Patient projection updated: %s", data["patient_id"])
        except Exception as e:
            logger.error("Error handling PatientUpdated: %s", e)
            raise

    return handle


def _make_user_deactivated_handler(session_factory, publisher):
    async def handle(body: bytes) -> None:
        """Auto-cancel future appointments when a user is deactivated."""
        try:
            data = json.loads(body)
            user_id = data.get("user_id")

            from datetime import datetime, timezone
            from sqlalchemy import select
            from app.domain.models.clinical import Appointment, PatientProjection

            async with session_factory() as session:
                # Get patient_id from projection
                result = await session.execute(
                    select(PatientProjection).where(PatientProjection.user_id == user_id)
                )
                proj = result.scalar_one_or_none()
                if not proj:
                    return

                now = datetime.now(timezone.utc)
                result = await session.execute(
                    select(Appointment).where(
                        Appointment.patient_id == proj.id,
                        Appointment.status.in_(["SCHEDULED", "CONFIRMED"]),
                        Appointment.scheduled_at > now,
                    )
                )
                appointments = result.scalars().all()
                for appt in appointments:
                    appt.status = "CANCELLED"
                    appt.cancellation_reason = "Usuário desativado"
                    appt.cancelled_at = now
                await session.commit()
                logger.info("Cancelled %d future appointments for user %s", len(appointments), user_id)
        except Exception as e:
            logger.error("Error handling UserDeactivated: %s", e)
            raise

    return handle
