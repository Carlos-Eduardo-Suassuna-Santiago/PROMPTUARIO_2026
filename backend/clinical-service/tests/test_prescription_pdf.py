"""
Tests for Prescription PDF generation, S3 upload, and download URL.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.exceptions import HTTPException

from app.config import settings
from app.domain.models.clinical import Prescription
from app.domain.models.schemas import MedicationItem, PrescriptionCreate
from app.domain.services.clinical_service import (
    PrescriptionService,
    _generate_prescription_pdf,
    _upload_pdf_to_s3,
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
def prescription_service(mock_session, mock_publisher):
    svc = PrescriptionService(mock_session, mock_publisher)
    svc.record_repo.get = AsyncMock(return_value=MagicMock(
        id="rec_123",
        patient_id="pat_123",
        doctor_id="doc_456",
    ))
    svc.rx_repo.add_history = AsyncMock()
    return svc


class TestPdfGeneration:
    def test_generate_prescription_pdf_returns_bytes(self):
        """Should generate valid PDF bytes from a prescription."""
        rx = Prescription(
            id=str(uuid.uuid4()),
            record_id="rec_123",
            patient_id="pat_123",
            doctor_id="doc_456",
            medications=[
                {"name": "Losartana", "dosage": "50mg", "frequency": "1x/dia", "duration_days": 30},
                {"name": "Omeprazol", "dosage": "20mg", "frequency": "1x/dia", "duration_days": 60},
            ],
            instructions="Tomar após o café da manhã",
            valid_days=30,
            created_at=datetime.now(timezone.utc),
        )

        pdf_bytes = _generate_prescription_pdf(rx, doctor_name="Dr. Silva")

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 100  # PDF should have substantial content
        assert pdf_bytes.startswith(b"%PDF")  # Valid PDF header

    def test_generate_prescription_pdf_with_single_medication(self):
        """Should handle prescriptions with a single medication."""
        rx = Prescription(
            id=str(uuid.uuid4()),
            record_id="rec_123",
            patient_id="pat_123",
            doctor_id="doc_456",
            medications=[{"name": "Dipirona", "dosage": "500mg", "frequency": "6/6h", "duration_days": 5}],
            instructions="Se houver febre",
            valid_days=30,
            created_at=datetime.now(timezone.utc),
        )

        pdf_bytes = _generate_prescription_pdf(rx, doctor_name="Dr. Silva")
        assert pdf_bytes.startswith(b"%PDF")

    def test_generate_prescription_pdf_empty_medications(self):
        """Should handle prescriptions with no medications gracefully."""
        rx = Prescription(
            id=str(uuid.uuid4()),
            record_id="rec_123",
            patient_id="pat_123",
            doctor_id="doc_456",
            medications=[],
            instructions="Nenhum medicamento",
            valid_days=30,
            created_at=datetime.now(timezone.utc),
        )

        pdf_bytes = _generate_prescription_pdf(rx, doctor_name="Dr. Silva")
        assert pdf_bytes.startswith(b"%PDF")


class TestPdfUpload:
    @patch("app.domain.services.clinical_service._get_s3_client")
    def test_upload_pdf_to_s3_success(self, mock_get_s3):
        """Should upload PDF to S3 and return the key."""
        s3_client = MagicMock()
        mock_get_s3.return_value = s3_client

        rx_id = str(uuid.uuid4())
        pdf_bytes = b"%PDF-1.4 fake content"

        s3_key = _upload_pdf_to_s3(rx_id, pdf_bytes)

        assert s3_key is not None
        assert rx_id in s3_key
        assert s3_key.endswith(".pdf")
        assert s3_key.startswith("prescriptions/")

        s3_client.put_object.assert_called_once()
        args, kwargs = s3_client.put_object.call_args
        assert kwargs["Bucket"] == settings.S3_BUCKET_PRESCRIPTIONS
        assert kwargs["Body"] == pdf_bytes
        assert kwargs["ContentType"] == "application/pdf"

    @patch("app.domain.services.clinical_service._get_s3_client")
    def test_upload_pdf_to_s3_failure(self, mock_get_s3):
        """Should return None on S3 failure (non-fatal)."""
        from botocore.exceptions import ClientError
        s3_client = MagicMock()
        s3_client.put_object.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Internal Error"}}, "PutObject"
        )
        mock_get_s3.return_value = s3_client

        s3_key = _upload_pdf_to_s3(str(uuid.uuid4()), b"fake-pdf")
        assert s3_key is None


class TestPrescriptionCreate:
    async def test_create_with_pdf_generation(self, prescription_service, mock_session):
        """Should create prescription, generate PDF, upload to S3, and record history."""
        data = PrescriptionCreate(
            medications=[MedicationItem(name="Losartana", dosage="50mg", frequency="1x/dia")],
            instructions="Tomar diariamente",
            valid_days=30,
        )

        with patch("app.domain.services.clinical_service._generate_prescription_pdf") as mock_gen_pdf, \
             patch("app.domain.services.clinical_service._upload_pdf_to_s3") as mock_upload:

            mock_gen_pdf.return_value = b"%PDF-1.4 fake content"
            mock_upload.return_value = f"prescriptions/{uuid.uuid4()[:2]}/{uuid.uuid4()}.pdf"

            rx = await prescription_service.create("rec_123", data, "doc_456")

            assert rx.record_id == "rec_123"
            assert rx.patient_id == "pat_123"
            assert rx.doctor_id == "doc_456"
            assert len(rx.medications) == 1
            assert rx.pdf_s3_key is not None
            assert rx.pdf_generated_at is not None
            assert rx.signature_hash is not None
            assert rx.signed_by == "doc_456"

            # Verify PDF was generated
            mock_gen_pdf.assert_called_once()
            mock_upload.assert_called_once()

            # Verify audit history was recorded
            prescription_service.rx_repo.add_history.assert_called_once()

    async def test_create_without_pdf_when_disabled(self, prescription_service, mock_session):
        """Should skip PDF generation when disabled in settings."""
        with patch.object(settings, "PDF_GENERATION_ENABLED", False):
            data = PrescriptionCreate(
                medications=[MedicationItem(name="Dipirona", dosage="500mg", frequency="6/6h")],
                valid_days=30,
            )

            rx = await prescription_service.create("rec_123", data, "doc_456")

            assert rx.pdf_s3_key is None
            assert rx.pdf_generated_at is None

    async def test_create_record_not_found(self, prescription_service):
        """Should raise 404 when medical record does not exist."""
        prescription_service.record_repo.get = AsyncMock(return_value=None)
        data = PrescriptionCreate(
            medications=[MedicationItem(name="Remédio", dosage="10mg", frequency="1x")],
            valid_days=30,
        )
        with pytest.raises(HTTPException) as exc:
            await prescription_service.create("invalid_rec", data, "doc_456")
        assert exc.value.status_code == 404

    async def test_create_doctor_not_authorized(self, prescription_service):
        """Should raise 403 when doctor is not the record's doctor."""
        prescription_service.record_repo.get = AsyncMock(return_value=MagicMock(
            doctor_id="other_doc"
        ))
        data = PrescriptionCreate(
            medications=[MedicationItem(name="Remédio", dosage="10mg", frequency="1x")],
            valid_days=30,
        )
        with pytest.raises(HTTPException) as exc:
            await prescription_service.create("rec_123", data, "doc_456")
        assert exc.value.status_code == 403


class TestPrescriptionDownload:
    async def test_get_pdf_download_url(self, prescription_service):
        """Should generate a pre-signed S3 URL for the prescription PDF."""
        rx = Prescription(
            id=str(uuid.uuid4()),
            record_id="rec_123",
            patient_id="pat_123",
            doctor_id="doc_456",
            medications=[],
            pdf_s3_key="prescriptions/ab/cd/rx_id.pdf",
            created_at=datetime.now(timezone.utc),
        )
        prescription_service.rx_repo.get = AsyncMock(return_value=rx)

        with patch("app.domain.services.clinical_service._get_s3_client") as mock_s3:
            s3_client = MagicMock()
            s3_client.generate_presigned_url.return_value = "https://s3.example.com/prescription.pdf"
            mock_s3.return_value = s3_client

            url = await prescription_service.get_pdf_download_url(rx.id)
            assert url == "https://s3.example.com/prescription.pdf"

            s3_client.generate_presigned_url.assert_called_once_with(
                "get_object",
                Params={
                    "Bucket": settings.S3_BUCKET_PRESCRIPTIONS,
                    "Key": rx.pdf_s3_key,
                    "ResponseContentDisposition": f'inline; filename="prescricao_{rx.id}.pdf"',
                },
                ExpiresIn=settings.S3_PRESIGNED_URL_EXPIRY,
            )

    async def test_get_pdf_download_url_no_pdf(self, prescription_service):
        """Should raise 400 when PDF has not been generated."""
        rx = Prescription(
            id=str(uuid.uuid4()),
            record_id="rec_123",
            patient_id="pat_123",
            doctor_id="doc_456",
            medications=[],
            pdf_s3_key=None,
            created_at=datetime.now(timezone.utc),
        )
        prescription_service.rx_repo.get = AsyncMock(return_value=rx)

        with pytest.raises(HTTPException) as exc:
            await prescription_service.get_pdf_download_url(rx.id)
        assert exc.value.status_code == 400
        assert "PDF ainda não foi gerado" in exc.value.detail

    async def test_get_pdf_download_url_not_found(self, prescription_service):
        """Should raise 404 when prescription does not exist."""
        prescription_service.rx_repo.get = AsyncMock(return_value=None)
        with pytest.raises(HTTPException) as exc:
            await prescription_service.get_pdf_download_url("invalid_rx")
        assert exc.value.status_code == 404