from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ReportExportRequest(BaseModel):
    """Request to generate an export (existing endpoint, extended with XLSX)."""
    report_type: Literal["CONSULTATIONS", "PATIENTS", "DOCTORS", "PRESCRIPTIONS", "CUSTOM", "FULL_SYSTEM"]
    output_format: Literal["JSON", "CSV", "PDF", "XLSX"] = "XLSX"
    parameters: dict = Field(default_factory=dict)


class CustomReportRequest(BaseModel):
    """Request for a parameterized custom report with validated query parameters."""
    report_type: Literal["CUSTOM"] = "CUSTOM"
    output_format: Literal["JSON", "CSV", "PDF", "XLSX"] = "XLSX"
    sql_query_name: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Name of the pre-approved SQL template (not raw SQL)",
    )
    parameters: dict = Field(
        default_factory=dict,
        description="Only string/number/bool values allowed. Keys must match template placeholders.",
    )

    @field_validator("parameters")
    @classmethod
    def validate_parameters_safe(cls, v: dict) -> dict:
        allowed_types = (str, int, float, bool)
        for key, val in v.items():
            if not isinstance(val, allowed_types):
                raise ValueError(
                    f"Parameter '{key}' has unsupported type {type(val).__name__}. "
                    f"Only str, int, float, bool allowed."
                )
            if isinstance(val, str) and len(val) > 500:
                raise ValueError(f"Parameter '{key}' exceeds 500 characters")
        return v


class MultiSheetExportRequest(BaseModel):
    """Request to export data across multiple sheets in a single XLSX workbook."""
    output_format: Literal["XLSX"] = "XLSX"
    sheets: list[SheetDefinition] = Field(..., min_length=1, max_length=20)
    filename: str = Field("multi_sheet_report.xlsx", max_length=120)

    @field_validator("filename")
    @classmethod
    def filename_must_end_with_xlsx(cls, v: str) -> str:
        if not v.endswith(".xlsx"):
            raise ValueError("Filename must end with .xlsx")
        return v


class SheetDefinition(BaseModel):
    sheet_name: str = Field(..., min_length=1, max_length=31, description="Excel sheet name (max 31 chars)")
    report_type: Literal["CONSULTATIONS", "PATIENTS", "DOCTORS", "PRESCRIPTIONS", "CUSTOM", "FULL_SYSTEM"]
    parameters: dict = Field(default_factory=dict)
    sql_query_name: Optional[str] = Field(None, max_length=64)


class ReportJobResponse(BaseModel):
    id: str
    report_type: str
    status: str
    output_format: str
    row_count: int
    s3_key: Optional[str] = None
    result_data: Optional[Any] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    model_config = {"from_attributes": True}