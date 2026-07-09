"""
Tests for rich notes sanitization and digital signature of medical records.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.exceptions import HTTPException

from app.domain.models.clinical import MedicalRecord
from app.domain.models.schemas import MedicalRecordCreate, MedicalRecordUpdate
from app.domain.services.clinical_service import (
    MedicalRecordService,
    _sanitize_rich_notes,
    _compute_signature_hash,
)


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def mock_publisher():
    return AsyncMock()


@pytest.fixture
def record_service(mock_session, mock_publisher):
    svc = MedicalRecordService(mock_session, mock_publisher)
    svc.appt_repo.get = AsyncMock(return_value=MagicMock(
        id="appt_123",
        patient_id="pat_123",
        doctor_id="doc_456",
    ))
    svc.appt_repo.update = AsyncMock()
    svc.repo.get_by_appointment = AsyncMock(return_value=None)
    svc.repo.create = AsyncMock()
    svc.repo.update = AsyncMock()
    svc.repo.add_history = AsyncMock()
    return svc


# ─── Rich Notes Sanitization ─────────────────────────────────────────────────

class TestRichNotesSanitization:
    def test_sanitize_removes_script_tags(self):
        """Should remove <script> tags from rich notes."""
        notes = {
            "section1": "<p>Normal text</p><script>alert('xss')</script>",
            "section2": "Clean text",
        }
        result = _sanitize_rich_notes(notes)
        assert "alert" not in result["section1"]
        assert "<script>" not in result["section1"]
        assert "Normal text" in result["section1"]

    def test_sanitize_removes_event_handlers(self):
        """Should remove inline event handlers like onload, onclick."""
        notes = {
            "content": '<img src="x" onerror="alert(1)" onclick="hack()">',
        }
        result = _sanitize_rich_notes(notes)
        assert "onerror" not in result["content"]
        assert "onclick" not in result["content"]

    def test_sanitize_escapes_html_tags(self):
        """Should escape < and > to prevent HTML injection."""
        notes = {
            "note": "<b>Bold</b> <i>Italic</i>",
        }
        result = _sanitize_rich_notes(notes)
        assert "<b>" not in result["note"]
        assert "<b>" in result["note"] or "<b>" in result["note"]

    def test_sanitize_limits_field_size(self):
        """Should truncate strings longer than 10000 chars."""
        long_text = "A" * 20000
        notes = {"long_field": long_text}
        result = _sanitize_rich_notes(notes)
        assert len(result["long_field"]) <= 10000

    def test_sanitize_none_returns_none(self):
        """Should return None for None input."""
        assert _sanitize_rich_notes(None) is None

    def test_sanitize_non_dict_returns_none(self):
        """Should return None for non-dict input."""
        assert _sanitize_rich_notes("not a dict") is None

    def test_sanitize_nested_dict(self):
        """Should sanitize nested dictionaries recursively."""
        notes = {
            "outer": {
                "inner": "<script>alert(1)</script>Safe text",
            }
        }
        result = _sanitize_rich_notes(notes)
        assert "<script>" not in result["outer"]["inner"]
        assert "Safe text" in result["outer"]["inner"]

    def test_sanitize_list_values(self):
        """Should sanitize values inside lists."""
        notes = {
            "items": ["<script>alert(1)</script>", "safe", "<img onerror='hack()'>"],
        }
        result = _sanitize_rich_notes(notes)
        for item in result["items"]:
            assert "<script>" not in item
            assert "onerror" not in item


# ─── Digital Signature ───────────────────────────────────────────────────────

class TestSignatureComputation:
    def test_compute_signature_hash_is_deterministic(self):
        """Should produce the same hash for identical content."""
        record = MedicalRecord(
            id="rec_123",
            patient_id="pat_123",
            doctor_id="doc_456",
            chief_complaint="Dor de cabeça",
            anamnesis="Há 3 dias",
            physical_exam="Normal",
            diagnosis="Enxaqueca",
            diagnosis_codes=["G43.009"],
            treatment_plan="Repouso",
            observations="Paciente estável",
            rich_notes={"sintomas": "cefaleia bilateral"},
        )

        hash1 = _compute_signature_hash(record)
        hash2 = _compute_signature_hash(record)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest

    def test_compute_signature_hash_changes_with_content(self):
        """Should produce different hashes for different content."""
        record1 = MedicalRecord(
            id="rec_123",
            patient_id="pat_123",
            doctor_id="doc_456",
            chief_complaint="Dor de cabeça",
        )
        record2 = MedicalRecord(
            id="rec_123",
            patient_id="pat_123",
            doctor_id="doc_456",
            chief_complaint="Dor abdominal",
        )

        hash1 = _compute_signature_hash(record1)
        hash2 = _compute_signature_hash(record2)
        assert hash1 != hash2

    def test_compute_signature_hash_includes_rich_notes(self):
        """Should include rich_notes in the hash computation."""
        record1 = MedicalRecord(
            id="rec_123",
            patient_id="pat_123",
            doctor_id="doc_456",
            chief_complaint="Dor",
            rich_notes={"obs": "Paciente melhorou"},
        )
        record2 = MedicalRecord(
            id="rec_123",
            patient_id="pat_123",
            doctor_id="doc_456",
            chief_complaint="Dor",
            rich_notes={"obs": "Paciente piorou"},
        )

        hash1 = _compute_signature_hash(record1)
        hash2 = _compute_signature_hash(record2)
        assert hash1 != hash2


class TestMedicalRecordSign:
    async def test_sign_record_success(self, record_service):
        """Should compute and store signature hash."""
        record = MedicalRecord(
            id="rec_123",
            patient_id="pat_123",
            doctor_id="doc_456",
            chief_complaint="Dor de cabeça",
        )
        record_service.repo.get = AsyncMock(return_value=record)
        record_service.repo.update = AsyncMock(return_value=record)

        signed = await record_service.sign("rec_123", "doc_456")

        assert signed.signature_hash is not None
        assert len(signed.signature_hash) == 64
        assert signed.signed_by == "doc_456"
        assert signed.signed_at is not None

        # Verify history was recorded
        record_service.repo.add_history.assert_called_once()
        history = record_service.repo.add_history.call_args[0][0]
        assert history.change_type == "SIGNED"
        assert history.snapshot["signature_hash"] == signed.signature_hash

    async def test_sign_record_not_found(self, record_service):
        """Should raise 404 when record does not exist."""
        record_service.repo.get = AsyncMock(return_value=None)
        with pytest.raises(HTTPException) as exc:
            await record_service.sign("invalid_rec", "doc_456")
        assert exc.value.status_code == 404

    async def test_sign_record_not_authorized(self, record_service):
        """Should raise 403 when doctor is not the record's doctor."""
        record = MedicalRecord(
            id="rec_123",
            patient_id="pat_123",
            doctor_id="other_doc",
            chief_complaint="Dor",
        )
        record_service.repo.get = AsyncMock(return_value=record)
        with pytest.raises(HTTPException) as exc:
            await record_service.sign("rec_123", "doc_456")
        assert exc.value.status_code == 403


class TestSignatureVerification:
    async def test_verify_signature_valid(self, record_service):
        """Should return verified=True when signature matches."""
        record = MedicalRecord(
            id="rec_123",
            patient_id="pat_123",
            doctor_id="doc_456",
            chief_complaint="Dor de cabeça",
            signature_hash="computed_hash_placeholder",
            signed_by="doc_456",
            signed_at=datetime.now(timezone.utc),
        )
        # Compute the real hash
        real_hash = _compute_signature_hash(record)
        record.signature_hash = real_hash

        record_service.repo.get = AsyncMock(return_value=record)

        result = await record_service.verify_signature("rec_123")
        assert result["verified"] is True
        assert result["reason"] == "Integridade confirmada"
        assert result["signed_by"] == "doc_456"

    async def test_verify_signature_tampered(self, record_service):
        """Should return verified=False when content was modified after signing."""
        record = MedicalRecord(
            id="rec_123",
            patient_id="pat_123",
            doctor_id="doc_456",
            chief_complaint="Dor de cabeça",
            signature_hash="tampered_hash_that_does_not_match",
            signed_by="doc_456",
            signed_at=datetime.now(timezone.utc),
        )
        record_service.repo.get = AsyncMock(return_value=record)

        result = await record_service.verify_signature("rec_123")
        assert result["verified"] is False
        assert "alterado após a assinatura" in result["reason"]

    async def test_verify_signature_not_signed(self, record_service):
        """Should return verified=False when record was never signed."""
        record = MedicalRecord(
            id="rec_123",
            patient_id="pat_123",
            doctor_id="doc_456",
            chief_complaint="Dor",
            signature_hash=None,
        )
        record_service.repo.get = AsyncMock(return_value=record)

        result = await record_service.verify_signature("rec_123")
        assert result["verified"] is False
        assert "não assinado" in result["reason"]

    async def test_verify_signature_not_found(self, record_service):
        """Should raise 404 when record does not exist."""
        record_service.repo.get = AsyncMock(return_value=None)
        with pytest.raises(HTTPException) as exc:
            await record_service.verify_signature("invalid_rec")
        assert exc.value.status_code == 404


class TestSignatureInvalidationOnUpdate:
    async def test_update_invalidates_signature(self, record_service):
        """Should clear signature when record is updated after signing."""
        record = MedicalRecord(
            id="rec_123",
            patient_id="pat_123",
            doctor_id="doc_456",
            chief_complaint="Dor de cabeça",
            signature_hash="existing_hash",
            signed_by="doc_456",
            signed_at=datetime.now(timezone.utc),
        )
        record_service.repo.get = AsyncMock(return_value=record)
        record_service.repo.update = AsyncMock(return_value=record)

        data = MedicalRecordUpdate(observations="Paciente melhorou")
        updated = await record_service.update("rec_123", data, "doc_456")

        assert updated.signature_hash is None
        assert updated.signed_by is None
        assert updated.signed_at is None