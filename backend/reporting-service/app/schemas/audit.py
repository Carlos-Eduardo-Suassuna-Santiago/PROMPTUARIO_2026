from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AuditEntryResponse(BaseModel):
    """Schema for a single audit log entry."""
    id: str
    event_type: str
    entity_type: str
    entity_id: Optional[str] = None
    description: str
    performed_by: str
    metadata: dict = {}
    ip_address: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class AuditLogSummary(BaseModel):
    """Summary of audit events grouped by type."""
    total: int
    by_event_type: dict[str, int]
    by_user: dict[str, int]
    period_start: str
    period_end: str