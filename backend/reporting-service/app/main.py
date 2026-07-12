from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import asyncpg
import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import func, select, text

from app.config import settings
from app.domain.models.report import (
    DailyStats,
    ReportJob,
    ReportSchedule,
    WebhookConfig,
    WebhookDeliveryLog,
    ReportAuditLog,
)
from app.schemas import (
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
    ScheduleListResponse,
    WebhookConfigCreate,
    WebhookConfigUpdate,
    WebhookConfigResponse,
    WebhookDeliveryLogResponse,
    ReportExportRequest,
    CustomReportRequest,
    MultiSheetExportRequest,
    ReportJobResponse,
    AuditEntryResponse,
    AuditLogSummary,
)
from app.workers.celery_tasks import celery_app
from shared.events import (
    AppointmentCancelledEvent,
    AppointmentCreatedEvent,
    MedicalRecordCreatedEvent,
    PatientCreatedEvent,
    PrescriptionGeneratedEvent,
)
from shared.events.broker import EventConsumer, EventPublisher
from shared.middleware.auth import make_auth_dependency
from shared.models.database import Base, build_engine, build_session_factory
from shared.metrics import reports_generated_total, reports_errors_total
from shared.observability import setup_observability
from app.config import settings as _settings

logger = logging.getLogger(__name__)

get_current_user, require_roles = make_auth_dependency(
    settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM
)

# ─── Reports Router ──────────────────────────────────────────────────────────

router = APIRouter(prefix="/reports", tags=["Reports"])


def _sf(r: Request):
    return r.app.state.session_factory


# ─── Export (existing, extended with XLSX and CUSTOM) ────────────────────────

@router.post(
    "/export",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_roles("ADMIN", "DOCTOR"))],
)
async def request_report(body: ReportExportRequest, request: Request, user=Depends(get_current_user)):
    async with _sf(request)() as session:
        job = ReportJob(
            id=str(uuid.uuid4()),
            report_type=body.report_type,
            output_format=body.output_format,
            parameters=body.parameters,
            requested_by=user.sub,
        )
        session.add(job)
        await session.commit()

        # Audit
        session.add(ReportAuditLog(
            id=str(uuid.uuid4()),
            event_type="REPORT_REQUESTED",
            entity_type="report_job",
            entity_id=job.id,
            description=f"Report requested: {body.report_type} ({body.output_format})",
            performed_by=user.sub,
            metadata={"report_type": body.report_type, "output_format": body.output_format,
                      "parameters": body.parameters},
            ip_address=request.client.host if request.client else None,
        ))
        await session.commit()

    reports_generated_total.labels(
        service=_settings.SERVICE_NAME,
        report_type=body.report_type,
        output_format=body.output_format,
    ).inc()

    celery_app.send_task("reporting.generate_report", args=[job.id])
    return {"job_id": job.id, "status": "PENDING"}


@router.post(
    "/export/custom",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_roles("ADMIN", "DOCTOR"))],
)
async def request_custom_report(body: CustomReportRequest, request: Request, user=Depends(get_current_user)):
    """Request a custom report using a pre-approved SQL template."""
    if body.sql_query_name not in settings.CUSTOM_SQL_TEMPLATES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown query template '{body.sql_query_name}'. "
                   f"Available: {list(settings.CUSTOM_SQL_TEMPLATES.keys())}",
        )

    async with _sf(request)() as session:
        job = ReportJob(
            id=str(uuid.uuid4()),
            report_type="CUSTOM",
            output_format=body.output_format,
            parameters={"sql_query_name": body.sql_query_name, **body.parameters},
            requested_by=user.sub,
        )
        session.add(job)
        await session.commit()

        session.add(ReportAuditLog(
            id=str(uuid.uuid4()),
            event_type="CUSTOM_REPORT_REQUESTED",
            entity_type="report_job",
            entity_id=job.id,
            description=f"Custom report: {body.sql_query_name} ({body.output_format})",
            performed_by=user.sub,
            metadata={"sql_query_name": body.sql_query_name, "output_format": body.output_format,
                      "parameters": body.parameters},
            ip_address=request.client.host if request.client else None,
        ))
        await session.commit()

    celery_app.send_task("reporting.generate_report", args=[job.id])
    return {"job_id": job.id, "status": "PENDING", "query_template": body.sql_query_name}


@router.post(
    "/export/multi-sheet",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_roles("ADMIN", "DOCTOR"))],
)
async def request_multi_sheet_export(body: MultiSheetExportRequest, request: Request, user=Depends(get_current_user)):
    """Request an XLSX export with multiple sheets."""
    async with _sf(request)() as session:
        job = ReportJob(
            id=str(uuid.uuid4()),
            report_type="CUSTOM",
            output_format="XLSX",
            parameters={"filename": body.filename, "sheets": [s.model_dump() for s in body.sheets]},
            requested_by=user.sub,
        )
        session.add(job)
        await session.commit()

        session.add(ReportAuditLog(
            id=str(uuid.uuid4()),
            event_type="MULTI_SHEET_REQUESTED",
            entity_type="report_job",
            entity_id=job.id,
            description=f"Multi-sheet XLSX: {len(body.sheets)} sheets",
            performed_by=user.sub,
            metadata={"filename": body.filename, "sheet_count": len(body.sheets)},
            ip_address=request.client.host if request.client else None,
        ))
        await session.commit()

    sheets_def = [s.model_dump() for s in body.sheets]
    celery_app.send_task("reporting.generate_multi_sheet", args=[job.id, sheets_def])
    return {"job_id": job.id, "status": "PENDING", "sheets": len(body.sheets)}


@router.get(
    "/export/{job_id}",
    response_model=ReportJobResponse,
    dependencies=[Depends(require_roles("ADMIN", "DOCTOR"))],
)
async def get_report_job(job_id: str, request: Request):
    async with _sf(request)() as session:
        result = await session.execute(select(ReportJob).where(ReportJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job não encontrado")
        return ReportJobResponse.model_validate(job)


@router.get(
    "/export/{job_id}/download",
    dependencies=[Depends(require_roles("ADMIN", "DOCTOR"))],
)
async def download_report(job_id: str, request: Request):
    async with _sf(request)() as session:
        result = await session.execute(select(ReportJob).where(ReportJob.id == job_id))
        job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if job.status != "COMPLETED":
        raise HTTPException(status_code=400, detail=f"Relatório ainda não concluído: {job.status}")
    if not job.s3_key:
        raise HTTPException(status_code=400, detail="Arquivo não disponível (JSON output)")

    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_REPORTS, "Key": job.s3_key},
        ExpiresIn=300,
    )
    return RedirectResponse(url=url, status_code=302)


# ─── Schedule Management ─────────────────────────────────────────────────────

schedule_router = APIRouter(prefix="/schedules", tags=["Schedules"])


@schedule_router.post(
    "",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def create_schedule(body: ScheduleCreate, request: Request, user=Depends(get_current_user)):
    async with _sf(request)() as session:
        sched = ReportSchedule(
            id=str(uuid.uuid4()),
            name=body.name,
            report_type=body.report_type,
            output_format=body.output_format,
            cron_expression=body.cron_expression,
            parameters=body.parameters,
            recipients=body.recipients,
            active=body.active,
            created_by=user.sub,
        )
        session.add(sched)
        await session.commit()
        await session.refresh(sched)

        session.add(ReportAuditLog(
            id=str(uuid.uuid4()),
            event_type="SCHEDULE_CREATED",
            entity_type="report_schedule",
            entity_id=sched.id,
            description=f"Schedule created: {body.name} ({body.cron_expression})",
            performed_by=user.sub,
            metadata={"name": body.name, "report_type": body.report_type,
                      "cron_expression": body.cron_expression},
            ip_address=request.client.host if request.client else None,
        ))
        await session.commit()

    # Refresh Celery Beat schedules
    celery_app.send_task("reporting.refresh_beat_schedules")
    return ScheduleResponse.model_validate(sched)


@schedule_router.get(
    "",
    response_model=ScheduleListResponse,
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def list_schedules(request: Request, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    async with _sf(request)() as session:
        offset = (page - 1) * size
        result = await session.execute(
            select(ReportSchedule).order_by(ReportSchedule.created_at.desc()).offset(offset).limit(size)
        )
        items = result.scalars().all()
        total_result = await session.execute(select(func.count(ReportSchedule.id)))
        total = total_result.scalar() or 0
        return ScheduleListResponse(
            items=[ScheduleResponse.model_validate(s) for s in items],
            total=total,
        )


@schedule_router.get(
    "/{schedule_id}",
    response_model=ScheduleResponse,
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def get_schedule(schedule_id: str, request: Request):
    async with _sf(request)() as session:
        result = await session.execute(select(ReportSchedule).where(ReportSchedule.id == schedule_id))
        sched = result.scalar_one_or_none()
        if not sched:
            raise HTTPException(status_code=404, detail="Schedule not found")
        return ScheduleResponse.model_validate(sched)


@schedule_router.put(
    "/{schedule_id}",
    response_model=ScheduleResponse,
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def update_schedule(schedule_id: str, body: ScheduleUpdate, request: Request, user=Depends(get_current_user)):
    async with _sf(request)() as session:
        result = await session.execute(select(ReportSchedule).where(ReportSchedule.id == schedule_id))
        sched = result.scalar_one_or_none()
        if not sched:
            raise HTTPException(status_code=404, detail="Schedule not found")

        update_data = body.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(sched, field, value)

        await session.commit()
        await session.refresh(sched)

        session.add(ReportAuditLog(
            id=str(uuid.uuid4()),
            event_type="SCHEDULE_UPDATED",
            entity_type="report_schedule",
            entity_id=sched.id,
            description=f"Schedule updated: {sched.name}",
            performed_by=user.sub,
            metadata={"updated_fields": list(update_data.keys())},
            ip_address=request.client.host if request.client else None,
        ))
        await session.commit()

    celery_app.send_task("reporting.refresh_beat_schedules")
    return ScheduleResponse.model_validate(sched)


@schedule_router.delete(
    "/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def delete_schedule(schedule_id: str, request: Request, user=Depends(get_current_user)):
    async with _sf(request)() as session:
        result = await session.execute(select(ReportSchedule).where(ReportSchedule.id == schedule_id))
        sched = result.scalar_one_or_none()
        if not sched:
            raise HTTPException(status_code=404, detail="Schedule not found")

        await session.delete(sched)
        await session.commit()

        session.add(ReportAuditLog(
            id=str(uuid.uuid4()),
            event_type="SCHEDULE_DELETED",
            entity_type="report_schedule",
            entity_id=schedule_id,
            description=f"Schedule deleted: {sched.name}",
            performed_by=user.sub,
            ip_address=request.client.host if request.client else None,
        ))
        await session.commit()

    celery_app.send_task("reporting.refresh_beat_schedules")


@schedule_router.post(
    "/{schedule_id}/trigger",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def trigger_schedule_now(schedule_id: str, request: Request, user=Depends(get_current_user)):
    """Manually trigger a scheduled report immediately."""
    async with _sf(request)() as session:
        result = await session.execute(select(ReportSchedule).where(ReportSchedule.id == schedule_id))
        sched = result.scalar_one_or_none()
        if not sched:
            raise HTTPException(status_code=404, detail="Schedule not found")

        job = ReportJob(
            id=str(uuid.uuid4()),
            report_type=sched.report_type,
            output_format=sched.output_format,
            parameters=sched.parameters,
            requested_by=user.sub,
            schedule_id=schedule_id,
        )
        session.add(job)
        await session.commit()

        session.add(ReportAuditLog(
            id=str(uuid.uuid4()),
            event_type="SCHEDULE_MANUAL_TRIGGER",
            entity_type="report_schedule",
            entity_id=schedule_id,
            description=f"Manual trigger of schedule: {sched.name}",
            performed_by=user.sub,
            metadata={"job_id": job.id},
            ip_address=request.client.host if request.client else None,
        ))
        await session.commit()

    celery_app.send_task("reporting.generate_report", args=[job.id])
    return {"job_id": job.id, "status": "PENDING", "schedule_id": schedule_id}


# ─── Webhook Management ──────────────────────────────────────────────────────

webhook_router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@webhook_router.post(
    "",
    response_model=WebhookConfigResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def create_webhook(body: WebhookConfigCreate, request: Request, user=Depends(get_current_user)):
    async with _sf(request)() as session:
        wh = WebhookConfig(
            id=str(uuid.uuid4()),
            url=str(body.url),
            secret=body.secret,
            description=body.description,
            active=body.active,
            max_retries=body.max_retries,
            retry_interval_seconds=body.retry_interval_seconds,
            events=body.events,
            created_by=user.sub,
        )
        session.add(wh)
        await session.commit()
        await session.refresh(wh)

        session.add(ReportAuditLog(
            id=str(uuid.uuid4()),
            event_type="WEBHOOK_CREATED",
            entity_type="webhook_config",
            entity_id=wh.id,
            description=f"Webhook created: {wh.url}",
            performed_by=user.sub,
            metadata={"url": str(body.url), "events": body.events},
            ip_address=request.client.host if request.client else None,
        ))
        await session.commit()

    return WebhookConfigResponse.model_validate(wh)


@webhook_router.get(
    "",
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def list_webhooks(request: Request):
    async with _sf(request)() as session:
        result = await session.execute(select(WebhookConfig).order_by(WebhookConfig.created_at.desc()))
        items = result.scalars().all()
        return {"items": [WebhookConfigResponse.model_validate(w) for w in items], "total": len(items)}


@webhook_router.get(
    "/{webhook_id}",
    response_model=WebhookConfigResponse,
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def get_webhook(webhook_id: str, request: Request):
    async with _sf(request)() as session:
        result = await session.execute(select(WebhookConfig).where(WebhookConfig.id == webhook_id))
        wh = result.scalar_one_or_none()
        if not wh:
            raise HTTPException(status_code=404, detail="Webhook not found")
        return WebhookConfigResponse.model_validate(wh)


@webhook_router.put(
    "/{webhook_id}",
    response_model=WebhookConfigResponse,
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def update_webhook(webhook_id: str, body: WebhookConfigUpdate, request: Request, user=Depends(get_current_user)):
    async with _sf(request)() as session:
        result = await session.execute(select(WebhookConfig).where(WebhookConfig.id == webhook_id))
        wh = result.scalar_one_or_none()
        if not wh:
            raise HTTPException(status_code=404, detail="Webhook not found")

        update_data = body.model_dump(exclude_unset=True)
        if "url" in update_data:
            update_data["url"] = str(update_data["url"])
        for field, value in update_data.items():
            setattr(wh, field, value)

        await session.commit()
        await session.refresh(wh)

        session.add(ReportAuditLog(
            id=str(uuid.uuid4()),
            event_type="WEBHOOK_UPDATED",
            entity_type="webhook_config",
            entity_id=wh.id,
            description=f"Webhook updated: {wh.url}",
            performed_by=user.sub,
            metadata={"updated_fields": list(update_data.keys())},
            ip_address=request.client.host if request.client else None,
        ))
        await session.commit()

    return WebhookConfigResponse.model_validate(wh)


@webhook_router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def delete_webhook(webhook_id: str, request: Request, user=Depends(get_current_user)):
    async with _sf(request)() as session:
        result = await session.execute(select(WebhookConfig).where(WebhookConfig.id == webhook_id))
        wh = result.scalar_one_or_none()
        if not wh:
            raise HTTPException(status_code=404, detail="Webhook not found")

        await session.delete(wh)
        await session.commit()

        session.add(ReportAuditLog(
            id=str(uuid.uuid4()),
            event_type="WEBHOOK_DELETED",
            entity_type="webhook_config",
            entity_id=webhook_id,
            description=f"Webhook deleted: {wh.url}",
            performed_by=user.sub,
            ip_address=request.client.host if request.client else None,
        ))
        await session.commit()


@webhook_router.get(
    "/{webhook_id}/deliveries",
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def list_webhook_deliveries(
    webhook_id: str,
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    async with _sf(request)() as session:
        offset = (page - 1) * size
        result = await session.execute(
            select(WebhookDeliveryLog)
            .where(WebhookDeliveryLog.webhook_config_id == webhook_id)
            .order_by(WebhookDeliveryLog.delivered_at.desc())
            .offset(offset)
            .limit(size)
        )
        items = result.scalars().all()
        total_result = await session.execute(
            select(func.count(WebhookDeliveryLog.id))
            .where(WebhookDeliveryLog.webhook_config_id == webhook_id)
        )
        total = total_result.scalar() or 0
        return {
            "items": [WebhookDeliveryLogResponse.model_validate(d) for d in items],
            "total": total,
            "page": page,
            "size": size,
        }


# ─── Audit Logs (Reporting-specific) ─────────────────────────────────────────

audit_router = APIRouter(prefix="/audit", tags=["Auditoria"])


@audit_router.get(
    "/logs",
    summary="Consultar logs de auditoria do reporting service",
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def get_report_audit_logs(
    request: Request,
    event_type: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
):
    async with _sf(request)() as session:
        q = select(ReportAuditLog)
        if event_type:
            q = q.where(ReportAuditLog.event_type == event_type)
        if entity_type:
            q = q.where(ReportAuditLog.entity_type == entity_type)
        if from_date:
            q = q.where(ReportAuditLog.created_at >= from_date)
        if to_date:
            q = q.where(ReportAuditLog.created_at <= to_date)

        total_result = await session.execute(select(func.count()).select_from(q.subquery()))
        total = total_result.scalar() or 0

        offset = (page - 1) * size
        result = await session.execute(
            q.order_by(ReportAuditLog.created_at.desc()).offset(offset).limit(size)
        )
        items = result.scalars().all()

        return {
            "items": [AuditEntryResponse.model_validate(a) for a in items],
            "total": total,
            "page": page,
            "size": size,
        }


@audit_router.get(
    "/summary",
    summary="Resumo de auditoria do reporting service",
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def get_report_audit_summary(
    request: Request,
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
):
    if not from_date:
        from_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    if not to_date:
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    async with _sf(request)() as session:
        rows = await session.execute(
            select(ReportAuditLog.event_type, func.count().label("cnt"))
            .where(ReportAuditLog.created_at >= from_date)
            .where(ReportAuditLog.created_at <= to_date)
            .group_by(ReportAuditLog.event_type)
        )
        by_event = {r.event_type: r.cnt for r in rows.fetchall()}

        user_rows = await session.execute(
            select(ReportAuditLog.performed_by, func.count().label("cnt"))
            .where(ReportAuditLog.created_at >= from_date)
            .where(ReportAuditLog.created_at <= to_date)
            .group_by(ReportAuditLog.performed_by)
        )
        by_user = {r.performed_by: r.cnt for r in user_rows.fetchall()}

        total_result = await session.execute(
            select(func.count(ReportAuditLog.id))
            .where(ReportAuditLog.created_at >= from_date)
            .where(ReportAuditLog.created_at <= to_date)
        )
        total = total_result.scalar() or 0

    return AuditLogSummary(
        total=total,
        by_event_type=by_event,
        by_user=by_user,
        period_start=from_date,
        period_end=to_date,
    )


# ─── Existing Dashboard / Stats endpoints ────────────────────────────────────

@router.get(
    "/consultations",
    dependencies=[Depends(require_roles("ADMIN", "DOCTOR"))],
)
async def consultations_report(
    request: Request,
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
):
    async with _sf(request)() as session:
        q = select(DailyStats).where(DailyStats.stat_type == "CONSULTATIONS")
        if from_date:
            q = q.where(DailyStats.stat_date >= from_date)
        if to_date:
            q = q.where(DailyStats.stat_date <= to_date)
        result = await session.execute(q.order_by(DailyStats.stat_date.desc()).limit(90))
        rows = result.scalars().all()
        return {"data": [{"date": r.stat_date, "consultations": r.value} for r in rows], "total_days": len(rows)}


@router.get(
    "/patients",
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def patients_report(
    request: Request,
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
):
    async with _sf(request)() as session:
        q = select(DailyStats).where(DailyStats.stat_type == "NEW_PATIENTS")
        if from_date:
            q = q.where(DailyStats.stat_date >= from_date)
        if to_date:
            q = q.where(DailyStats.stat_date <= to_date)
        result = await session.execute(q.order_by(DailyStats.stat_date.desc()).limit(90))
        rows = result.scalars().all()
        total = sum(r.value for r in rows)
        return {"data": [{"date": r.stat_date, "new_patients": r.value} for r in rows], "total_new_patients": total}


@router.get(
    "/doctors",
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def doctors_report(
    request: Request,
    doctor_id: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
):
    async with _sf(request)() as session:
        q = select(DailyStats).where(DailyStats.stat_type == "DOCTOR_CONSULTATIONS")
        if doctor_id:
            q = q.where(DailyStats.entity_id == doctor_id)
        if from_date:
            q = q.where(DailyStats.stat_date >= from_date)
        if to_date:
            q = q.where(DailyStats.stat_date <= to_date)
        result = await session.execute(q.order_by(DailyStats.stat_date.desc()).limit(200))
        rows = result.scalars().all()
        return {"data": [{"doctor_id": r.entity_id, "date": r.stat_date, "consultations": r.value} for r in rows]}


@router.get(
    "/summary",
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def dashboard_summary(request: Request):
    async with _sf(request)() as session:
        today = datetime.now(timezone.utc).date().isoformat()
        consultations_today = await session.scalar(
            select(func.sum(DailyStats.value)).where(DailyStats.stat_type == "CONSULTATIONS", DailyStats.stat_date == today)
        ) or 0
        new_patients_month = await session.scalar(
            select(func.sum(DailyStats.value)).where(DailyStats.stat_type == "NEW_PATIENTS", DailyStats.stat_date >= today[:7] + "-01")
        ) or 0
        cancellations_today = await session.scalar(
            select(func.sum(DailyStats.value)).where(DailyStats.stat_type == "CANCELLATIONS", DailyStats.stat_date == today)
        ) or 0
        return {"consultations_today": consultations_today, "new_patients_this_month": new_patients_month, "cancellations_today": cancellations_today, "as_of": datetime.now(timezone.utc).isoformat()}


# ─── Cross-service Audit Router (existing) ───────────────────────────────────

audit_cross_router = APIRouter(prefix="/audit", tags=["Auditoria"])


def _get_db_urls() -> dict[str, str]:
    return {
        "iam":      settings.IAM_DB_URL,
        "patient":  settings.PATIENT_DB_URL,
        "clinical": settings.CLINICAL_DB_URL,
    }


@audit_cross_router.get(
    "/cross/logs",
    summary="Consultar logs de auditoria (cross-service)",
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def get_audit_logs(
    service: Optional[str] = Query(None, description="iam | patient | clinical | all"),
    table_name: Optional[str] = Query(None),
    operation: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
):
    db_urls = _get_db_urls()
    services = [service] if service and service != "all" else list(db_urls.keys())
    all_logs: list[dict] = []

    for svc in services:
        if svc not in db_urls:
            continue
        try:
            conn = await asyncpg.connect(db_urls[svc])
            try:
                conditions = ["1=1"]
                values: list = []
                if table_name:
                    conditions.append(f"table_name = ${len(values)+1}")
                    values.append(table_name)
                if operation:
                    conditions.append(f"operation = ${len(values)+1}")
                    values.append(operation)
                if user_id:
                    conditions.append(f"user_id = ${len(values)+1}")
                    values.append(user_id)
                if from_date:
                    conditions.append(f"timestamp::date >= ${len(values)+1}::date")
                    values.append(from_date)
                if to_date:
                    conditions.append(f"timestamp::date <= ${len(values)+1}::date")
                    values.append(to_date)

                where = " AND ".join(conditions)
                offset = (page - 1) * size

                rows = await conn.fetch(
                    f"SELECT * FROM audit_logs WHERE {where} "
                    f"ORDER BY timestamp DESC "
                    f"LIMIT ${len(values)+1} OFFSET ${len(values)+2}",
                    *values, size, offset,
                )
                all_logs.extend([dict(r) for r in rows])
            finally:
                await conn.close()
        except Exception as exc:
            logger.warning("Erro ao consultar audit_logs de %s: %s", svc, exc)

    all_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return {"items": all_logs[:size], "total": len(all_logs), "page": page, "size": size}


@audit_cross_router.get(
    "/cross/summary",
    summary="Resumo de auditoria (cross-service)",
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def get_audit_summary(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
):
    if not from_date:
        from_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    if not to_date:
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    summary = {
        "period": {"from": from_date, "to": to_date},
        "total": 0,
        "by_operation": {},
        "by_service": {},
        "by_table": {},
    }

    for svc, url in _get_db_urls().items():
        try:
            conn = await asyncpg.connect(url)
            try:
                rows = await conn.fetch(
                    "SELECT operation, table_name, COUNT(*) AS cnt "
                    "FROM audit_logs "
                    "WHERE timestamp::date BETWEEN $1::date AND $2::date "
                    "GROUP BY operation, table_name",
                    from_date, to_date,
                )
                for row in rows:
                    cnt = row["cnt"]
                    summary["total"] += cnt
                    summary["by_operation"].setdefault(row["operation"], 0)
                    summary["by_operation"][row["operation"]] += cnt
                    summary["by_service"].setdefault(svc, 0)
                    summary["by_service"][svc] += cnt
                    summary["by_table"].setdefault(row["table_name"], 0)
                    summary["by_table"][row["table_name"]] += cnt
            finally:
                await conn.close()
        except Exception as exc:
            logger.warning("Erro ao resumir audit de %s: %s", svc, exc)

    return summary


@audit_cross_router.get(
    "/cross/suspicious",
    summary="Atividades suspeitas (cross-service)",
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def get_suspicious():
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    alerts: list[dict] = []

    for svc, url in _get_db_urls().items():
        try:
            conn = await asyncpg.connect(url)
            try:
                rows = await conn.fetch(
                    "SELECT user_id, user_email, COUNT(*) AS cnt, "
                    "date_trunc('hour', timestamp) AS hour "
                    "FROM audit_logs "
                    "WHERE operation = 'DELETE' AND timestamp > $1 "
                    "GROUP BY user_id, user_email, date_trunc('hour', timestamp) "
                    "HAVING COUNT(*) > 10",
                    cutoff,
                )
                for row in rows:
                    alerts.append({
                        "type": "EXCESSIVE_DELETES",
                        "severity": "HIGH",
                        "service": svc,
                        "user_id": row["user_id"],
                        "user_email": row["user_email"],
                        "count": row["cnt"],
                        "period_hour": str(row["hour"]),
                    })

                failed = await conn.fetch(
                    "SELECT user_email, COUNT(*) AS cnt "
                    "FROM audit_logs "
                    "WHERE operation = 'AUTH_LOGIN_FAILED' AND timestamp > $1 "
                    "GROUP BY user_email HAVING COUNT(*) > 5",
                    cutoff,
                )
                for row in failed:
                    alerts.append({
                        "type": "BRUTE_FORCE_ATTEMPT",
                        "severity": "CRITICAL",
                        "service": svc,
                        "user_email": row["user_email"],
                        "count": row["cnt"],
                    })
            finally:
                await conn.close()
        except Exception as exc:
            logger.warning("Erro ao verificar suspeitos em %s: %s", svc, exc)

    return {
        "alerts": alerts,
        "total_alerts": len(alerts),
        "period_days": 7,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ─── Event Consumers — update DailyStats ─────────────────────────────────────

def _setup_consumers(consumer: EventConsumer, session_factory) -> None:
    consumer.register(
        exchange=AppointmentCreatedEvent.EXCHANGE,
        routing_key=AppointmentCreatedEvent.ROUTING_KEY,
        handler=_make_stat_handler(session_factory, "CONSULTATIONS", "appointment_id"),
    )
    consumer.register(
        exchange=AppointmentCancelledEvent.EXCHANGE,
        routing_key=AppointmentCancelledEvent.ROUTING_KEY,
        handler=_make_stat_handler(session_factory, "CANCELLATIONS", "appointment_id"),
    )
    consumer.register(
        exchange=PatientCreatedEvent.EXCHANGE,
        routing_key=PatientCreatedEvent.ROUTING_KEY,
        handler=_make_stat_handler(session_factory, "NEW_PATIENTS", "patient_id"),
    )
    consumer.register(
        exchange=MedicalRecordCreatedEvent.EXCHANGE,
        routing_key=MedicalRecordCreatedEvent.ROUTING_KEY,
        handler=_make_doctor_stat_handler(session_factory),
    )


def _make_stat_handler(session_factory, stat_type: str, id_field: str):
    async def handle(body: bytes) -> None:
        try:
            data = json.loads(body)
            today = datetime.now(timezone.utc).date().isoformat()
            async with session_factory() as session:
                existing = await session.execute(
                    select(DailyStats).where(
                        DailyStats.stat_type == stat_type,
                        DailyStats.stat_date == today,
                        DailyStats.entity_id == None,
                    )
                )
                row = existing.scalar_one_or_none()
                if row:
                    row.value += 1
                else:
                    session.add(DailyStats(id=str(uuid.uuid4()), stat_date=today, stat_type=stat_type, value=1))
                await session.commit()
                logger.debug("Incremented %s for %s", stat_type, today)
        except Exception as e:
            logger.error("Error updating stat %s: %s", stat_type, e)
            raise
    return handle


def _make_doctor_stat_handler(session_factory):
    async def handle(body: bytes) -> None:
        try:
            data = json.loads(body)
            doctor_id = data.get("doctor_id")
            if not doctor_id:
                return
            today = datetime.now(timezone.utc).date().isoformat()
            async with session_factory() as session:
                existing = await session.execute(
                    select(DailyStats).where(
                        DailyStats.stat_type == "DOCTOR_CONSULTATIONS",
                        DailyStats.stat_date == today,
                        DailyStats.entity_id == doctor_id,
                    )
                )
                row = existing.scalar_one_or_none()
                if row:
                    row.value += 1
                else:
                    session.add(DailyStats(id=str(uuid.uuid4()), stat_date=today, stat_type="DOCTOR_CONSULTATIONS", entity_id=doctor_id, value=1))
                await session.commit()
        except Exception as e:
            logger.error("Error updating doctor stat: %s", e)
            raise
    return handle


# ─── Backup Admin Router ──────────────────────────────────────────────────────

backup_router = APIRouter(prefix="/admin/backups", tags=["Backup"])


@backup_router.get(
    "",
    summary="Listar backups disponíveis",
    dependencies=[Depends(require_roles("ADMIN"))],
)
async def list_backups():
    import boto3 as _boto3
    s3 = _boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
    try:
        response = s3.list_objects_v2(Bucket="backups")
        objects = response.get("Contents", [])
    except Exception as exc:
        logger.warning("Não foi possível listar backups: %s", exc)
        return {"items": [], "message": "Bucket de backups não acessível"}

    items = []
    for obj in sorted(objects, key=lambda x: x["LastModified"], reverse=True):
        try:
            url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": "backups", "Key": obj["Key"]},
                ExpiresIn=3600,
            )
        except Exception:
            url = None
        items.append({
            "filename": obj["Key"].split("/")[-1],
            "key": obj["Key"],
            "size_mb": round(obj["Size"] / 1_048_576, 2),
            "created_at": obj["LastModified"].isoformat(),
            "download_url": url,
        })
    return {"items": items, "total": len(items)}


# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="PROMPTUARIO — Reporting Service",
    description="Relatórios, exportações assíncronas, agendamento, webhooks e auditoria",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_observability(app, settings.SERVICE_NAME, settings.LOG_LEVEL)

app.include_router(router, prefix="/api/v1")
app.include_router(schedule_router, prefix="/api/v1")
app.include_router(webhook_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(audit_cross_router, prefix="/api/v1")
app.include_router(backup_router, prefix="/api/v1")


@app.on_event("startup")
async def startup():
    engine = build_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.state.session_factory = build_session_factory(engine)

    _ensure_s3_bucket()

    publisher = EventPublisher(settings.RABBITMQ_URL)
    await publisher.connect()
    app.state.publisher = publisher

    consumer = EventConsumer(settings.RABBITMQ_URL, settings.SERVICE_NAME)
    await consumer.connect()
    _setup_consumers(consumer, app.state.session_factory)
    await consumer.start()
    app.state.consumer = consumer

    logger.info("Reporting Service v2 started ✅ (scheduling, webhooks, XLSX, audit)")


@app.on_event("shutdown")
async def shutdown():
    await app.state.publisher.close()
    await app.state.consumer.close()


def _ensure_s3_bucket():
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
        )
        try:
            s3.head_bucket(Bucket=settings.S3_BUCKET_REPORTS)
        except ClientError:
            s3.create_bucket(Bucket=settings.S3_BUCKET_REPORTS)
            logger.info("S3 bucket created: %s", settings.S3_BUCKET_REPORTS)
    except Exception as e:
        logger.warning("Could not ensure S3 bucket (will retry): %s", e)


@app.get("/healthz", tags=["Health"])
async def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}