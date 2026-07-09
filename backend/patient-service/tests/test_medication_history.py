"""
Tests for Medication history tracking — create, update, deactivate, reactivate.
Verifies that each operation preserves an immutable history snapshot.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.exceptions import HTTPException

from app.domain.models.patient import ContinuousMedication, MedicationHistory
from app.domain.models.schemas import MedicationCreate, MedicationDeactivate, MedicationUpdate
from app.domain.services.patient_service import MedicationService


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def mock_publisher():
    return AsyncMock()


@pytest.fixture
def medication_service(mock_session, mock_publisher):
    svc = MedicationService(mock_session, mock_publisher)
    svc.patient_repo.get_by_id = AsyncMock(return_value=MagicMock(id="pat_123"))
    return svc


class TestMedicationCreate:
    async def test_create_with_history(self, medication_service):
        """Should create medication and record CREATED history entry."""
        med = ContinuousMedication(
            id=str(uuid.uuid4()),
            patient_id="pat_123",
            name="Losartana",
            dosage="50mg",
            frequency="1x ao dia",
            prescribing_doctor="Dr. Silva",
            started_at=date(2026, 1, 15),
            notes="Controle de pressão",
            version=1,
            active=True,
        )
        medication_service.repo.create = AsyncMock(return_value=med)
        medication_service.history_repo.create = AsyncMock()

        data = MedicationCreate(
            name="Losartana",
            dosage="50mg",
            frequency="1x ao dia",
            prescribing_doctor="Dr. Silva",
            started_at=date(2026, 1, 15),
            notes="Controle de pressão",
        )
        result = await medication_service.create("pat_123", data, changed_by="usr_456")

        assert result.name == "Losartana"
        assert result.version == 1
        assert result.active is True

        # Verify history was recorded
        medication_service.history_repo.create.assert_called_once()
        history = medication_service.history_repo.create.call_args[0][0]
        assert history.change_type == "CREATED"
        assert history.version == 1
        assert history.medication_id == med.id
        assert history.changed_by == "usr_456"

    async def test_create_patient_not_found(self, medication_service):
        """Should raise 404 when patient does not exist."""
        medication_service.patient_repo.get_by_id = AsyncMock(return_value=None)
        data = MedicationCreate(name="Remédio", dosage="10mg", frequency="1x")
        with pytest.raises(HTTPException) as exc:
            await medication_service.create("invalid_pat", data)
        assert exc.value.status_code == 404


class TestMedicationUpdate:
    async def test_update_with_history(self, medication_service):
        """Should update medication fields and record UPDATED history."""
        med = ContinuousMedication(
            id=str(uuid.uuid4()),
            patient_id="pat_123",
            name="Losartana",
            dosage="50mg",
            frequency="1x ao dia",
            version=1,
            active=True,
        )
        medication_service.repo.get = AsyncMock(return_value=med)
        medication_service.repo.update = AsyncMock()
        medication_service.history_repo.create = AsyncMock()

        data = MedicationUpdate(dosage="100mg", frequency="2x ao dia")
        result = await medication_service.update("pat_123", med.id, data, changed_by="usr_456")

        assert result.dosage == "100mg"
        assert result.frequency == "2x ao dia"
        assert result.version == 2

        # Verify history was recorded
        medication_service.history_repo.create.assert_called_once()
        history = medication_service.history_repo.create.call_args[0][0]
        assert history.change_type == "UPDATED"
        assert history.version == 2
        assert history.dosage == "100mg"
        assert history.frequency == "2x ao dia"

    async def test_update_not_found(self, medication_service):
        """Should raise 404 when medication does not exist."""
        medication_service.repo.get = AsyncMock(return_value=None)
        data = MedicationUpdate(dosage="100mg")
        with pytest.raises(HTTPException) as exc:
            await medication_service.update("pat_123", "invalid_med", data)
        assert exc.value.status_code == 404


class TestMedicationDeactivate:
    async def test_deactivate_with_history(self, medication_service):
        """Should deactivate medication and record DEACTIVATED history."""
        med = ContinuousMedication(
            id=str(uuid.uuid4()),
            patient_id="pat_123",
            name="Losartana",
            dosage="50mg",
            frequency="1x ao dia",
            version=1,
            active=True,
        )
        medication_service.repo.get = AsyncMock(return_value=med)
        medication_service.repo.update = AsyncMock()
        medication_service.history_repo.create = AsyncMock()

        data = MedicationDeactivate(
            ended_at=date(2026, 6, 1),
            end_reason="Troca de medicamento",
        )
        result = await medication_service.deactivate("pat_123", med.id, data, changed_by="usr_456")

        assert result.active is False
        assert result.ended_at == date(2026, 6, 1)
        assert result.end_reason == "Troca de medicamento"
        assert result.version == 2

        # Verify history
        medication_service.history_repo.create.assert_called_once()
        history = medication_service.history_repo.create.call_args[0][0]
        assert history.change_type == "DEACTIVATED"
        assert history.version == 2
        assert history.ended_at == date(2026, 6, 1)
        assert history.end_reason == "Troca de medicamento"

    async def test_deactivate_default_end_date(self, medication_service):
        """Should use current date when no end_date provided."""
        med = ContinuousMedication(
            id=str(uuid.uuid4()),
            patient_id="pat_123",
            name="Losartana",
            dosage="50mg",
            frequency="1x ao dia",
            version=1,
            active=True,
        )
        medication_service.repo.get = AsyncMock(return_value=med)
        medication_service.repo.update = AsyncMock()
        medication_service.history_repo.create = AsyncMock()

        result = await medication_service.deactivate("pat_123", med.id, changed_by="usr_456")
        assert result.active is False
        assert result.ended_at == date.today()
        assert result.end_reason is None


class TestMedicationReactivate:
    async def test_reactivate_with_history(self, medication_service):
        """Should reactivate medication and record REACTIVATED history."""
        med = ContinuousMedication(
            id=str(uuid.uuid4()),
            patient_id="pat_123",
            name="Losartana",
            dosage="50mg",
            frequency="1x ao dia",
            version=2,
            active=False,
            ended_at=date(2026, 6, 1),
            end_reason="Troca de medicamento",
        )
        medication_service.repo.get = AsyncMock(return_value=med)
        medication_service.repo.update = AsyncMock()
        medication_service.history_repo.create = AsyncMock()

        result = await medication_service.reactivate("pat_123", med.id, changed_by="usr_456")

        assert result.active is True
        assert result.ended_at is None
        assert result.end_reason is None
        assert result.version == 3

        # Verify history
        medication_service.history_repo.create.assert_called_once()
        history = medication_service.history_repo.create.call_args[0][0]
        assert history.change_type == "REACTIVATED"
        assert history.version == 3


class TestMedicationHistory:
    async def test_get_history_by_patient(self, medication_service):
        """Should return all history entries for a patient."""
        mock_history = [
            MedicationHistory(
                id=str(uuid.uuid4()),
                patient_id="pat_123",
                medication_id=str(uuid.uuid4()),
                name="Losartana",
                dosage="50mg",
                frequency="1x ao dia",
                version=1,
                change_type="CREATED",
                created_at=datetime.now(timezone.utc),
            ),
            MedicationHistory(
                id=str(uuid.uuid4()),
                patient_id="pat_123",
                medication_id=str(uuid.uuid4()),
                name="Losartana",
                dosage="100mg",
                frequency="2x ao dia",
                version=2,
                change_type="UPDATED",
                created_at=datetime.now(timezone.utc),
            ),
        ]
        medication_service.history_repo.list_by_patient = AsyncMock(return_value=mock_history)

        history = await medication_service.get_history("pat_123")
        assert len(history) == 2
        assert history[0].change_type == "CREATED"
        assert history[1].change_type == "UPDATED"

    async def test_get_history_by_medication(self, medication_service):
        """Should return history entries for a specific medication."""
        med_id = str(uuid.uuid4())
        mock_history = [
            MedicationHistory(
                id=str(uuid.uuid4()),
                patient_id="pat_123",
                medication_id=med_id,
                name="Losartana",
                dosage="50mg",
                frequency="1x ao dia",
                version=1,
                change_type="CREATED",
                created_at=datetime.now(timezone.utc),
            ),
        ]
        medication_service.history_repo.list_by_medication = AsyncMock(return_value=mock_history)

        history = await medication_service.get_history("pat_123", medication_id=med_id)
        assert len(history) == 1
        assert history[0].medication_id == med_id
        medication_service.history_repo.list_by_medication.assert_called_once_with(med_id)