from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class WebhookConfigCreate(BaseModel):
    """Payload to register a webhook endpoint for job completion notifications."""
    url: HttpUrl
    secret: str = Field(..., min_length=16, max_length=128, description="Shared secret for HMAC signing")
    description: str = Field("", max_length=255)
    active: bool = True
    max_retries: int = Field(3, ge=0, le=10)
    retry_interval_seconds: int = Field(60, ge=10, le=3600)
    events: list[str] = Field(
        default_factory=lambda: ["report.completed"],
        description="Event types to subscribe to (e.g. report.completed, report.failed)",
    )


class WebhookConfigUpdate(BaseModel):
    url: Optional[HttpUrl] = None
    secret: Optional[str] = Field(None, min_length=16, max_length=128)
    description: Optional[str] = Field(None, max_length=255)
    active: Optional[bool] = None
    max_retries: Optional[int] = Field(None, ge=0, le=10)
    retry_interval_seconds: Optional[int] = Field(None, ge=10, le=3600)
    events: Optional[list[str]] = None


class WebhookConfigResponse(BaseModel):
    id: str
    url: str
    description: str
    active: bool
    max_retries: int
    retry_interval_seconds: int
    events: list[str]
    last_delivery_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    consecutive_failures: int = 0
    created_by: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class WebhookDeliveryLogResponse(BaseModel):
    id: str
    webhook_config_id: str
    job_id: str
    event_type: str
    url: str
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    success: bool
    attempt: int
    error_message: Optional[str] = None
    delivered_at: datetime
    model_config = {"from_attributes": True}