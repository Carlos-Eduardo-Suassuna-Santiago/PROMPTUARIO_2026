"""Unit tests for the new Pydantic schemas (scheduling, webhooks, custom reports, XLSX)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.schedule import ScheduleCreate, ScheduleUpdate
from app.schemas.webhook import WebhookConfigCreate, WebhookConfigUpdate
from app.schemas.report import (
    ReportExportRequest,
    CustomReportRequest,
    MultiSheetExportRequest,
    SheetDefinition,
)
from app.schemas.audit import AuditEntryResponse, AuditLogSummary


class TestScheduleSchemas:
    def test_valid_schedule_create(self):
        s = ScheduleCreate(
            name="Daily Consultations",
            report_type="CONSULTATIONS",
            output_format="XLSX",
            cron_expression="0 6 * * *",
        )
        assert s.name == "Daily Consultations"
        assert s.active is True
        assert s.recipients == []

    def test_invalid_cron_expression(self):
        with pytest.raises(ValidationError):
            ScheduleCreate(
                name="Bad Cron",
                report_type="PATIENTS",
                cron_expression="invalid cron",
            )

    def test_schedule_update_partial(self):
        u = ScheduleUpdate(name="Updated Name", active=False)
        assert u.name == "Updated Name"
        assert u.active is False
        assert u.report_type is None  # not provided

    def test_schedule_create_with_recipients(self):
        s = ScheduleCreate(
            name="Weekly",
            report_type="DOCTORS",
            output_format="PDF",
            cron_expression="30 9 * * 1",
            recipients=["admin@example.com"],
        )
        assert "admin@example.com" in s.recipients


class TestWebhookSchemas:
    def test_valid_webhook_create(self):
        wh = WebhookConfigCreate(
            url="https://hooks.example.com/report",
            secret="supersecret12345678",
            description="Production hook",
        )
        assert wh.active is True
        assert wh.max_retries == 3
        assert wh.retry_interval_seconds == 60

    def test_invalid_secret_too_short(self):
        with pytest.raises(ValidationError):
            WebhookConfigCreate(
                url="https://example.com/hook",
                secret="short",  # less than 16 chars
            )

    def test_webhook_update_partial(self):
        u = WebhookConfigUpdate(active=False)
        assert u.active is False
        assert u.url is None

    def test_webhook_with_custom_events(self):
        wh = WebhookConfigCreate(
            url="https://example.com/hook",
            secret="abcdef1234567890",
            events=["report.completed", "report.failed"],
        )
        assert "report.completed" in wh.events
        assert "report.failed" in wh.events


class TestReportSchemas:
    def test_export_request_defaults_to_xlsx(self):
        r = ReportExportRequest(report_type="CONSULTATIONS")
        assert r.output_format == "XLSX"

    def test_custom_report_valid(self):
        c = CustomReportRequest(
            sql_query_name="consultations_by_doctor",
            parameters={"from_date": "2025-01-01", "to_date": "2025-12-31"},
        )
        assert c.sql_query_name == "consultations_by_doctor"
        assert c.parameters["from_date"] == "2025-01-01"

    def test_custom_report_invalid_parameter_type(self):
        with pytest.raises(ValidationError, match="unsupported type"):
            CustomReportRequest(
                sql_query_name="consultations_by_doctor",
                parameters={"bad_param": [1, 2, 3]},  # list not allowed
            )

    def test_custom_report_invalid_parameter_too_long(self):
        with pytest.raises(ValidationError, match="exceeds 500 characters"):
            CustomReportRequest(
                sql_query_name="consultations_by_doctor",
                parameters={"x": "A" * 501},
            )

    def test_multi_sheet_export_valid(self):
        m = MultiSheetExportRequest(
            sheets=[
                SheetDefinition(sheet_name="Consults", report_type="CONSULTATIONS"),
                SheetDefinition(sheet_name="Patients", report_type="PATIENTS"),
            ],
            filename="my_report.xlsx",
        )
        assert len(m.sheets) == 2
        assert m.filename == "my_report.xlsx"

    def test_multi_sheet_invalid_filename(self):
        with pytest.raises(ValidationError, match="must end with .xlsx"):
            MultiSheetExportRequest(
                sheets=[SheetDefinition(sheet_name="Test", report_type="CONSULTATIONS")],
                filename="report.pdf",
            )

    def test_multi_sheet_too_many_sheets(self):
        with pytest.raises(ValidationError):
            MultiSheetExportRequest(
                sheets=[SheetDefinition(sheet_name=f"S{i}", report_type="CONSULTATIONS") for i in range(25)],
            )


class TestAuditSchemas:
    def test_audit_entry_response(self):
        from datetime import datetime, timezone
        entry = AuditEntryResponse(
            id="abc-123",
            event_type="REPORT_REQUESTED",
            entity_type="report_job",
            entity_id="job-1",
            description="Test",
            performed_by="user-1",
            created_at=datetime.now(timezone.utc),
        )
        assert entry.event_type == "REPORT_REQUESTED"

    def test_audit_summary(self):
        summary = AuditLogSummary(
            total=42,
            by_event_type={"REPORT_REQUESTED": 30, "REPORT_COMPLETED": 12},
            by_user={"admin": 42},
            period_start="2025-01-01",
            period_end="2025-01-31",
        )
        assert summary.total == 42