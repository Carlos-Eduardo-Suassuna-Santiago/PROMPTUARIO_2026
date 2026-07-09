"""
Tests for Patient Document upload, list, download URL, and soft-delete.
These tests use mock S3 (MinIO) via moto or direct in-memory mocking.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile
from fastapi.exceptions import HTTPException

from app.config import settings
from app.domain.models.patient import PatientDocument
from app.domain.services.patient_service import DocumentService


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def mock_publisher():
    return AsyncMock()


@pytest.fixture
def mock_patient():
    patient = MagicMock()
    patient.id = str(uuid.uuid4())
    patient.anonymized = False
    patient.is_active = True
    return patient


@pytest.fixture
def document_service(mock_session, mock_publisher):
    svc = DocumentService(mock_session, mock_publisher)
    svc.patient_repo.get_by_id = AsyncMock(return_value=mock_patient())
    return svc


class TestDocumentUpload:
    async def test_upload_success(self, document_service, mock_session):
        """Should upload file metadata to DB and return document record."""
        file = MagicMock(spec=UploadFile)
        file.filename = "exam_results.pdf"
        file.content_type = "application/pdf"
        file.read = AsyncMock(return_value=b"fake-pdf-content-12345")

        with patch("app.domain.services.patient_service._get_s3_client") as mock_s3:
            s3_client = MagicMock()
            mock_s3.return_value = s3_client

            doc = await document_service.upload(
                patient_id="pat_123",
                file=file,
                document_type="EXAM",
                description="Blood test results",
                uploaded_by="usr_456",
            )

            # Verify S3 put_object was called
            s3_client.put_object.assert_called_once()
            args, kwargs = s3_client.put_object.call_args
            assert kwargs["Bucket"] == settings.S3_BUCKET_PATIENT_DOCUMENTS
            assert kwargs["Body"] == b"fake-pdf-content-12345"
            assert kwargs["ContentType"] == "application/pdf"
            assert "patients/pat_123/documents/" in kwargs["Key"]

            # Verify DB record
            assert doc.patient_id == "pat_123"
            assert doc.file_name == "exam_results.pdf"
            assert doc.document_type == "EXAM"
            assert doc.file_size == 20
            assert doc.mime_type == "application/pdf"
            assert doc.file_hash is not None
            assert doc.description == "Blood test results"
            assert doc.uploaded_by == "usr_456"
            assert doc.is_active is True

    async def test_upload_invalid_mime_type(self, document_service):
        """Should reject files with disallowed mime types."""
        file = MagicMock(spec=UploadFile)
        file.filename = "malware.exe"
        file.content_type = "application/x-msdownload"
        file.read = AsyncMock(return_value=b"evil-code")

        with pytest.raises(HTTPException) as exc:
            await document_service.upload(
                patient_id="pat_123",
                file=file,
                document_type="EXAM",
            )
        assert exc.value.status_code == 400
        assert "não permitido" in exc.value.detail

    async def test_upload_file_too_large(self, document_service):
        """Should reject files exceeding MAX_DOCUMENT_SIZE_MB."""
        large_content = b"x" * ((settings.MAX_DOCUMENT_SIZE_MB * 1024 * 1024) + 1)
        file = MagicMock(spec=UploadFile)
        file.filename = "large_file.pdf"
        file.content_type = "application/pdf"
        file.read = AsyncMock(return_value=large_content)

        with pytest.raises(HTTPException) as exc:
            await document_service.upload(
                patient_id="pat_123",
                file=file,
                document_type="EXAM",
            )
        assert exc.value.status_code == 400
        assert "muito grande" in exc.value.detail

    async def test_upload_anonymized_patient(self, document_service):
        """Should reject upload for anonymized patients."""
        document_service.patient_repo.get_by_id = AsyncMock(
            return_value=MagicMock(anonymized=True)
        )
        file = MagicMock(spec=UploadFile)
        file.filename = "doc.pdf"
        file.content_type = "application/pdf"
        file.read = AsyncMock(return_value=b"content")

        with pytest.raises(HTTPException) as exc:
            await document_service.upload(
                patient_id="pat_123",
                file=file,
                document_type="EXAM",
            )
        assert exc.value.status_code == 403


class TestDocumentList:
    async def test_list_documents(self, document_service, mock_session):
        """Should return paginated list of documents."""
        mock_docs = [
            PatientDocument(
                id=str(uuid.uuid4()),
                patient_id="pat_123",
                document_type="EXAM",
                file_name="test1.pdf",
                s3_key=f"patients/pat_123/documents/doc1.pdf",
                file_size=100,
                mime_type="application/pdf",
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ),
            PatientDocument(
                id=str(uuid.uuid4()),
                patient_id="pat_123",
                document_type="REPORT",
                file_name="report2.pdf",
                s3_key=f"patients/pat_123/documents/doc2.pdf",
                file_size=200,
                mime_type="application/pdf",
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ),
        ]

        with patch.object(document_service.repo, "list_by_patient", AsyncMock(return_value=(mock_docs, 2))):
            items, total = await document_service.list("pat_123", page=1, size=10)
            assert total == 2
            assert len(items) == 2
            assert items[0].document_type == "EXAM"
            assert items[1].file_name == "report2.pdf"

    async def test_list_empty(self, document_service):
        """Should return empty list when no documents."""
        with patch.object(document_service.repo, "list_by_patient", AsyncMock(return_value=([], 0))):
            items, total = await document_service.list("pat_123")
            assert total == 0
            assert items == []


class TestDocumentDownload:
    async def test_get_download_url(self, document_service):
        """Should generate a pre-signed S3 URL."""
        doc = PatientDocument(
            id=str(uuid.uuid4()),
            patient_id="pat_123",
            document_type="EXAM",
            file_name="report.pdf",
            s3_key="patients/pat_123/documents/doc.pdf",
            file_size=100,
            mime_type="application/pdf",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        document_service.repo.get = AsyncMock(return_value=doc)

        with patch("app.domain.services.patient_service._get_s3_client") as mock_s3:
            s3_client = MagicMock()
            s3_client.generate_presigned_url.return_value = "https://s3.example.com/download-url"
            mock_s3.return_value = s3_client

            url = await document_service.get_download_url("pat_123", doc.id)
            assert url == "https://s3.example.com/download-url"
            s3_client.generate_presigned_url.assert_called_once_with(
                "get_object",
                Params={
                    "Bucket": settings.S3_BUCKET_PATIENT_DOCUMENTS,
                    "Key": doc.s3_key,
                    "ResponseContentDisposition": f'attachment; filename="{doc.file_name}"',
                },
                ExpiresIn=settings.S3_PRESIGNED_URL_EXPIRY,
            )


class TestDocumentSoftDelete:
    async def test_soft_delete(self, document_service):
        """Should mark document as inactive and set deleted_at."""
        doc = PatientDocument(
            id=str(uuid.uuid4()),
            patient_id="pat_123",
            document_type="EXAM",
            file_name="test.pdf",
            s3_key="patients/pat_123/documents/test.pdf",
            file_size=100,
            mime_type="application/pdf",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        document_service.repo.get = AsyncMock(return_value=doc)

        updated_doc = PatientDocument(
            id=doc.id,
            patient_id="pat_123",
            document_type="EXAM",
            file_name="test.pdf",
            s3_key="patients/pat_123/documents/test.pdf",
            file_size=100,
            mime_type="application/pdf",
            is_active=False,
            deleted_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        document_service.repo.soft_delete = AsyncMock(return_value=updated_doc)

        await document_service.soft_delete("pat_123", doc.id)
        document_service.repo.soft_delete.assert_called_once_with(doc)