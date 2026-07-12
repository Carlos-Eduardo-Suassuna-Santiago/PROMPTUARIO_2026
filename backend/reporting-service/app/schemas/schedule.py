from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ScheduleCreate(BaseModel):
    """Payload to create a recurring report schedule."""
    name: str = Field(..., min_length=1, max_length=120, description="Human-friendly name")
    report_type: Literal["CONSULTATIONS", "PATIENTS", "DOCTORS", "PRESCRIPTIONS", "CUSTOM", "FULL_SYSTEM"]
    output_format: Literal["JSON", "CSV", "PDF", "XLSX"] = "XLSX"
    cron_expression: str = Field(
        ...,
        pattern=r"^(\S+\s+){4}\S+$",
        description="5-field cron expression (minute hour dom month dow)",
    )
    parameters: dict = Field(default_factory=dict)
    recipients: list[str] = Field(default_factory=list, description="Email addresses or webhook labels")
    active: bool = True


class ScheduleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    report_type: Optional[Literal["CONSULTATIONS", "PATIENTS", "DOCTORS", "PRESCRIPTIONS", "CUSTOM", "FULL_SYSTEM"]] = None
    output_format: Optional[Literal["JSON", "CSV", "PDF", "XLSX"]] = None
    cron_expression: Optional[str] = Field(
        None,
        pattern=r"^(\S+\s+){4}\S+$",
    )
    parameters: Optional[dict] = None
    recipients: Optional[list[str]] = None
    active: Optional[bool] = None


class ScheduleResponse(BaseModel):
    id: str
    name: str
    report_type: str
    output_format: str
    cron_expression: str
    parameters: dict
    recipients: list[str]
    active: bool
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_by: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class ScheduleListResponse(BaseModel):
    items: list[ScheduleResponse]
    total: int