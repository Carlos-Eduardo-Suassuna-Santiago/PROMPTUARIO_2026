"""
Celery async workers for report generation.
Runs in a separate container (reporting-worker).
Extended with: XLSX multi-sheet export, webhook dispatch, scheduled reports, custom SQL templates.
"""
from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
import httpx
from botocore.exceptions import ClientError
from celery import Celery
from celery.signals import beat_init
from sqlalchemy import text as sa_text

from app.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "reporting",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_s3():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )


def _ensure_bucket(s3_client, bucket: str) -> None:
    try:
        s3_client.head_bucket(Bucket=bucket)
    except ClientError:
        s3_client.create_bucket(Bucket=bucket)


def _get_sync_engine():
    """Synchronous SQLAlchemy engine for Celery tasks."""
    from sqlalchemy import create_engine
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    return create_engine(sync_url)


def _write_audit_log(session, event_type: str, entity_type: str, entity_id: str | None,
                     description: str, performed_by: str, metadata: dict | None = None,
                     ip_address: str | None = None) -> None:
    session.execute(
        sa_text("""
            INSERT INTO report_audit_logs (id, event_type, entity_type, entity_id,
                description, performed_by, metadata, ip_address, created_at)
            VALUES (:id, :event_type, :entity_type, :entity_id,
                :description, :performed_by, :metadata, :ip_address, :now)
        """),
        {
            "id": str(uuid.uuid4()),
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "description": description,
            "performed_by": performed_by,
            "metadata": json.dumps(metadata or {}),
            "ip_address": ip_address,
            "now": datetime.now(timezone.utc).isoformat(),
        },
    )
    session.commit()


# ─── Data Generation ──────────────────────────────────────────────────────────

def _generate_data(session, report_type: str, params: dict) -> list[dict]:
    """Generate report data from the reporting DB (pre-aggregated stats or custom SQL)."""
    from sqlalchemy import text as sa_text

    from_date = params.get("from_date", "2024-01-01")
    to_date = params.get("to_date", datetime.now(timezone.utc).date().isoformat())

    # ---- Custom SQL template ----
    if report_type == "CUSTOM":
        query_name = params.get("sql_query_name", "")
        template = settings.CUSTOM_SQL_TEMPLATES.get(query_name)
        if not template:
            raise ValueError(f"Unknown custom query template: '{query_name}'. "
                             f"Available: {list(settings.CUSTOM_SQL_TEMPLATES.keys())}")

        # Only allow params that are str/int/float/bool — validated upstream
        bind_params = {}
        allowed_placeholders = ["from_date", "to_date"]
        # Extract placeholders from template
        import re
        placeholders = re.findall(r':(\w+)', template)
        for ph in placeholders:
            if ph == "from_date":
                bind_params["from_date"] = from_date
            elif ph == "to_date":
                bind_params["to_date"] = to_date
            elif ph in params:
                val = params[ph]
                if isinstance(val, (str, int, float, bool)):
                    bind_params[ph] = val
                else:
                    raise ValueError(f"Invalid type for placeholder '{ph}'")

        rows = session.execute(sa_text(template), bind_params).fetchall()
        return [dict(r._mapping) for r in rows]

    # ---- Pre-defined report types ----
    if report_type == "CONSULTATIONS":
        rows = session.execute(
            sa_text("""
                SELECT stat_date, value as consultations, metadata
                FROM daily_stats
                WHERE stat_type = 'CONSULTATIONS'
                  AND stat_date BETWEEN :from_date AND :to_date
                ORDER BY stat_date DESC
            """),
            {"from_date": from_date, "to_date": to_date},
        ).fetchall()
        return [{"date": str(r.stat_date), "consultations": r.consultations} for r in rows]

    elif report_type == "PATIENTS":
        rows = session.execute(
            sa_text("""
                SELECT stat_date, value as new_patients
                FROM daily_stats
                WHERE stat_type = 'NEW_PATIENTS'
                  AND stat_date BETWEEN :from_date AND :to_date
                ORDER BY stat_date DESC
            """),
            {"from_date": from_date, "to_date": to_date},
        ).fetchall()
        return [{"date": str(r.stat_date), "new_patients": r.new_patients} for r in rows]

    elif report_type == "DOCTORS":
        doctor_id = params.get("doctor_id")
        q = """
            SELECT entity_id as doctor_id, stat_date, value as consultations
            FROM daily_stats
            WHERE stat_type = 'DOCTOR_CONSULTATIONS'
              AND stat_date BETWEEN :from_date AND :to_date
        """
        bind = {"from_date": from_date, "to_date": to_date}
        if doctor_id:
            q += " AND entity_id = :doctor_id"
            bind["doctor_id"] = doctor_id
        rows = session.execute(sa_text(q + " ORDER BY stat_date DESC"), bind).fetchall()
        return [{"doctor_id": r.doctor_id, "date": str(r.stat_date), "consultations": r.consultations} for r in rows]

    elif report_type == "PRESCRIPTIONS":
        rows = session.execute(
            sa_text("""
                SELECT stat_date, value as prescriptions
                FROM daily_stats
                WHERE stat_type = 'PRESCRIPTIONS'
                  AND stat_date BETWEEN :from_date AND :to_date
                ORDER BY stat_date DESC
            """),
            {"from_date": from_date, "to_date": to_date},
        ).fetchall()
        return [{"date": str(r.stat_date), "prescriptions": r.prescriptions} for r in rows]

    return []


# ─── Upload Helpers ───────────────────────────────────────────────────────────

def _upload_report(job_id: str, data: list, output_format: str, report_type: str) -> str:
    s3 = _get_s3()
    _ensure_bucket(s3, settings.S3_BUCKET_REPORTS)
    key = f"reports/{report_type.lower()}/{job_id}.{output_format.lower()}"

    if output_format == "CSV":
        content = _build_csv(data)

        s3.put_object(
            Bucket=settings.S3_BUCKET_REPORTS,
            Key=key,
            Body=content,
            ContentType="text/csv",
        )

    elif output_format == "PDF":
        key = _build_and_upload_pdf(s3, data, report_type, key)

    elif output_format == "XLSX":
        content = _build_xlsx(data, report_type)
        s3.put_object(
            Bucket=settings.S3_BUCKET_REPORTS,
            Key=key,
            Body=content,
            ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    return key


def _build_csv(data: list[dict]) -> bytes:
    if not data:
        return b""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)
    return buf.getvalue().encode("utf-8-sig")


def _build_xlsx(data: list[dict], sheet_name: str = "Report") -> bytes:
    """Build a single-sheet XLSX workbook from a list of dicts."""
    from app.infrastructure.xlsx_builder import build_xlsx as _build
    return _build(data, sheet_name)


def _build_multi_sheet_xlsx(sheets_data: list[dict]) -> bytes:
    """Build an XLSX workbook with multiple sheets."""
    from app.infrastructure.xlsx_builder import build_multi_sheet_xlsx as _build
    return _build(sheets_data)


def _build_and_upload_pdf(s3, data: list, report_type: str, key: str) -> str:
    """Simple HTML → PDF via weasyprint, fallback to JSON."""
    try:
        from weasyprint import HTML
        html = _data_to_html(data, report_type)
        pdf_bytes = HTML(string=html).write_pdf()
        s3.put_object(
            Bucket=settings.S3_BUCKET_REPORTS,
            Key=key,
            Body=pdf_bytes,
            ContentType="application/pdf",
        )
    except ImportError:
        logger.warning("WeasyPrint not installed, uploading JSON fallback")
        s3.put_object(
            Bucket=settings.S3_BUCKET_REPORTS,
            Key=key.replace(".pdf", ".json"),
            Body=json.dumps(data).encode(),
            ContentType="application/json",
        )
        return key.replace(".pdf", ".json")
    return key


def _data_to_html(data: list, report_type: str) -> str:
    if not data:
        return "<html><body><p>Sem dados</p></body></html>"
    headers = list(data[0].keys())
    rows = "".join(
        "<tr>" + "".join(f"<td>{row.get(h, '')}</td>" for h in headers) + "</tr>"
        for row in data
    )
    header_row = "".join(f"<th>{h}</th>" for h in headers)
    return f"""
    <html><head><meta charset='utf-8'>
    <style>body{{font-family:Arial;}} table{{border-collapse:collapse;width:100%;}}
    th,td{{border:1px solid #ddd;padding:8px;}} th{{background:#4A90D9;color:#fff;}}</style>
    </head><body>
    <h2>Relatório: {report_type}</h2>
    <table><thead><tr>{header_row}</tr></thead><tbody>{rows}</tbody></table>
    </body></html>
    """


# ─── Webhook Dispatch ─────────────────────────────────────────────────────────

def dispatch_webhooks(session, job_id: str, event_type: str, payload: dict) -> None:
    """Send webhook notifications for all active configs subscribed to event_type.
    Implements retry logic and logs delivery attempts."""
    rows = session.execute(
        sa_text("""
            SELECT id, url, secret, max_retries, retry_interval_seconds
            FROM webhook_configs
            WHERE active = true AND events @> :event_arr::jsonb
        """),
        {"event_arr": json.dumps([event_type])},
    ).fetchall()

    for row in rows:
        wh_id = row.id
        wh_url = row.url
        wh_secret = row.secret
        max_retries = row.max_retries
        retry_interval = row.retry_interval_seconds

        # Build signed payload
        body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(
            wh_secret.encode("utf-8"),
            body_bytes,
            hashlib.sha256,
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": f"sha256={signature}",
            "X-Webhook-Event": event_type,
            "X-Webhook-Job-Id": job_id,
        }

        success = False
        status_code = None
        response_body = None
        error_message = None

        for attempt in range(1, max_retries + 2):  # initial + retries
            try:
                resp = httpx.post(
                    wh_url,
                    content=body_bytes,
                    headers=headers,
                    timeout=30.0,
                )
                status_code = resp.status_code
                response_body = resp.text[:2000]
                if 200 <= resp.status_code < 300:
                    success = True
                    break
                else:
                    error_message = f"HTTP {resp.status_code}: {resp.text[:200]}"
            except httpx.RequestError as exc:
                error_message = str(exc)
                status_code = None

            if attempt <= max_retries:
                logger.warning("Webhook attempt %d/%d failed for %s: %s",
                               attempt, max_retries, wh_url, error_message)
                time.sleep(retry_interval)
            else:
                logger.error("Webhook exhausted retries for %s", wh_url)

        # Log delivery
        session.execute(
            sa_text("""
                INSERT INTO webhook_delivery_logs
                    (id, webhook_config_id, job_id, event_type, url,
                     status_code, response_body, success, attempt, error_message, delivered_at)
                VALUES (:id, :wh_id, :job_id, :event_type, :url,
                        :status_code, :response_body, :success, :attempt, :error_message, :now)
            """),
            {
                "id": str(uuid.uuid4()),
                "wh_id": wh_id,
                "job_id": job_id,
                "event_type": event_type,
                "url": wh_url,
                "status_code": status_code,
                "response_body": response_body,
                "success": success,
                "attempt": attempt,
                "error_message": error_message,
                "now": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Update config status
        session.execute(
            sa_text("""
                UPDATE webhook_configs
                SET last_delivery_at = :now,
                    last_success_at = CASE WHEN :success THEN :now ELSE last_success_at END,
                    consecutive_failures = CASE WHEN :success THEN 0 ELSE consecutive_failures + 1 END,
                    updated_at = :now
                WHERE id = :wh_id
            """),
            {
                "now": datetime.now(timezone.utc).isoformat(),
                "success": success,
                "wh_id": wh_id,
            },
        )

        _write_audit_log(
            session,
            event_type="WEBHOOK_SENT",
            entity_type="webhook_config",
            entity_id=wh_id,
            description=f"Webhook {'delivered' if success else 'failed'} to {wh_url} "
                        f"for job {job_id} (event={event_type})",
            performed_by="system",
            metadata={"job_id": job_id, "event_type": event_type, "success": success,
                      "status_code": status_code, "attempt": attempt},
        )

    session.commit()


# ─── Main Celery Task ─────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="reporting.generate_report", max_retries=3, default_retry_delay=60)
def generate_report(self, job_id: str) -> dict:
    """Main Celery task: generate a report and upload to S3."""
    from sqlalchemy.orm import Session

    engine = _get_sync_engine()
    logger.info("Generating report job: %s", job_id)

    with Session(engine) as session:
        job_row = session.execute(
            sa_text("SELECT * FROM report_jobs WHERE id = :id"), {"id": job_id}
        ).fetchone()

        if not job_row:
            logger.error("Report job not found: %s", job_id)
            return {"error": "Job not found"}

        session.execute(
            sa_text("UPDATE report_jobs SET status='RUNNING' WHERE id=:id"), {"id": job_id}
        )
        session.commit()
        _write_audit_log(session, "REPORT_STARTED", "report_job", job_id,
                         f"Report generation started: {job_row.report_type}", "system")

        try:
            params = job_row.parameters or {}
            report_type = job_row.report_type
            output_format = job_row.output_format

            data = _generate_data(session, report_type, params)
            s3_key = None
            row_count = len(data) if isinstance(data, list) else 1

            if output_format in ("CSV", "PDF", "XLSX"):
                s3_key = _upload_report(job_id, data, output_format, report_type)

            session.execute(
                sa_text("""
                    UPDATE report_jobs
                    SET status='COMPLETED', result_data=:data, s3_key=:s3_key,
                        row_count=:count, completed_at=:now
                    WHERE id=:id
                """),
                {
                    "data": json.dumps(data) if output_format == "JSON" else None,
                    "s3_key": s3_key,
                    "count": row_count,
                    "now": datetime.now(timezone.utc).isoformat(),
                    "id": job_id,
                },
            )
            session.commit()

            # Audit: completion
            _write_audit_log(session, "REPORT_COMPLETED", "report_job", job_id,
                             f"Report completed: {report_type} ({row_count} rows, {output_format})",
                             "system",
                             metadata={"row_count": row_count, "output_format": output_format,
                                       "s3_key": s3_key})

            # ── Dispatch webhooks ──
            payload = {
                "event": "report.completed",
                "job_id": job_id,
                "report_type": report_type,
                "output_format": output_format,
                "status": "COMPLETED",
                "row_count": row_count,
                "s3_key": s3_key,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            dispatch_webhooks(session, job_id, "report.completed", payload)

            # Mark webhook_triggered
            session.execute(
                sa_text("UPDATE report_jobs SET webhook_triggered = true WHERE id = :id"),
                {"id": job_id},
            )
            session.commit()

            logger.info("Report job completed: %s (%d rows)", job_id, row_count)
            return {"job_id": job_id, "status": "COMPLETED", "rows": row_count}

        except Exception as e:
            logger.error("Report generation failed for %s: %s", job_id, e)
            session.execute(
                sa_text("UPDATE report_jobs SET status='FAILED', error_message=:err WHERE id=:id"),
                {"err": str(e), "id": job_id},
            )
            session.commit()
            _write_audit_log(session, "REPORT_FAILED", "report_job", job_id,
                             f"Report failed: {str(e)[:200]}", "system",
                             metadata={"error": str(e)})

            # Dispatch failure webhook
            payload = {
                "event": "report.failed",
                "job_id": job_id,
                "report_type": job_row.report_type,
                "output_format": job_row.output_format,
                "status": "FAILED",
                "error": str(e)[:500],
                "failed_at": datetime.now(timezone.utc).isoformat(),
            }
            dispatch_webhooks(session, job_id, "report.failed", payload)

            raise self.retry(exc=e)


# ─── Multi-Sheet XLSX Task ────────────────────────────────────────────────────

@celery_app.task(bind=True, name="reporting.generate_multi_sheet", max_retries=3, default_retry_delay=60)
def generate_multi_sheet_report(self, job_id: str, sheets_def: list[dict]) -> dict:
    """Generate an XLSX workbook with multiple sheets from different queries."""
    from sqlalchemy.orm import Session

    engine = _get_sync_engine()
    logger.info("Generating multi-sheet report job: %s", job_id)

    with Session(engine) as session:
        job_row = session.execute(
            sa_text("SELECT * FROM report_jobs WHERE id = :id"), {"id": job_id}
        ).fetchone()
        if not job_row:
            return {"error": "Job not found"}

        session.execute(
            sa_text("UPDATE report_jobs SET status='RUNNING' WHERE id=:id"), {"id": job_id}
        )
        session.commit()

        try:
            sheets_data = []
            total_rows = 0
            for sheet_def in sheets_def:
                sheet_name = sheet_def.get("sheet_name", "Sheet")
                report_type = sheet_def.get("report_type", "CONSULTATIONS")
                params = sheet_def.get("parameters", {})
                data = _generate_data(session, report_type, params)
                total_rows += len(data)
                sheets_data.append({"sheet_name": sheet_name, "data": data})

            xlsx_bytes = _build_multi_sheet_xlsx(sheets_data)
            s3 = _get_s3()
            _ensure_bucket(s3, settings.S3_BUCKET_REPORTS)
            filename = job_row.parameters.get("filename", "multi_sheet_report.xlsx")
            s3_key = f"reports/multi_sheet/{job_id}/{filename}"
            s3.put_object(
                Bucket=settings.S3_BUCKET_REPORTS,
                Key=s3_key,
                Body=xlsx_bytes,
                ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            session.execute(
                sa_text("""
                    UPDATE report_jobs
                    SET status='COMPLETED', s3_key=:s3_key, row_count=:count, completed_at=:now
                    WHERE id=:id
                """),
                {"s3_key": s3_key, "count": total_rows,
                 "now": datetime.now(timezone.utc).isoformat(), "id": job_id},
            )
            session.commit()

            payload = {
                "event": "report.completed",
                "job_id": job_id,
                "report_type": "MULTI_SHEET",
                "output_format": "XLSX",
                "status": "COMPLETED",
                "row_count": total_rows,
                "s3_key": s3_key,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            dispatch_webhooks(session, job_id, "report.completed", payload)

            session.execute(
                sa_text("UPDATE report_jobs SET webhook_triggered = true WHERE id = :id"),
                {"id": job_id},
            )
            session.commit()

            logger.info("Multi-sheet report completed: %s (%d rows, %d sheets)",
                        job_id, total_rows, len(sheets_data))
            return {"job_id": job_id, "status": "COMPLETED", "rows": total_rows}

        except Exception as e:
            logger.error("Multi-sheet report failed: %s", e)
            session.execute(
                sa_text("UPDATE report_jobs SET status='FAILED', error_message=:err WHERE id=:id"),
                {"err": str(e), "id": job_id},
            )
            session.commit()
            raise self.retry(exc=e)


# ─── Scheduled Report Task ────────────────────────────────────────────────────

@celery_app.task(name="reporting.run_scheduled_report")
def run_scheduled_report(schedule_id: str) -> None:
    """Celery Beat task: triggered by cron schedule, creates a ReportJob and dispatches it."""
    from sqlalchemy.orm import Session

    engine = _get_sync_engine()
    logger.info("Running scheduled report: %s", schedule_id)

    with Session(engine) as session:
        sched = session.execute(
            sa_text("SELECT * FROM report_schedules WHERE id = :id AND active = true"),
            {"id": schedule_id},
        ).fetchone()

        if not sched:
            logger.warning("Schedule %s not found or inactive", schedule_id)
            return

        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Create job
        session.execute(
            sa_text("""
                INSERT INTO report_jobs (id, report_type, requested_by, parameters, status,
                    output_format, schedule_id, created_at)
                VALUES (:id, :report_type, :requested_by, :parameters, 'PENDING',
                    :output_format, :schedule_id, :now)
            """),
            {
                "id": job_id,
                "report_type": sched.report_type,
                "requested_by": "scheduler",
                "parameters": json.dumps(sched.parameters or {}),
                "output_format": sched.output_format,
                "schedule_id": schedule_id,
                "now": now,
            },
        )

        # Update schedule's last_run_at
        session.execute(
            sa_text("""
                UPDATE report_schedules
                SET last_run_at = :now, updated_at = :now
                WHERE id = :id
            """),
            {"now": now, "id": schedule_id},
        )
        session.commit()

        _write_audit_log(session, "SCHEDULE_TRIGGERED", "report_schedule", schedule_id,
                         f"Scheduled report triggered: {sched.name}", "system",
                         metadata={"job_id": job_id, "report_type": sched.report_type})

    # Dispatch the actual generation task
    celery_app.send_task("reporting.generate_report", args=[job_id])


# ─── Celery Beat Configuration ────────────────────────────────────────────────

@beat_init.connect
def on_beat_init(**kwargs):
    """Load schedules from the database on Celery Beat startup.
    This ensures dynamic schedules are registered without redeploying."""
    logger.info("Celery Beat initializing — syncing schedules from DB")
    _sync_beat_schedules()


def _sync_beat_schedules() -> None:
    """Read active schedules from DB and update Celery Beat's schedule."""
    try:
        from celery.beat import ScheduleEntry
        from celery.schedules import crontab

        engine = _get_sync_engine()
        from sqlalchemy.orm import Session

        entries: dict[str, ScheduleEntry] = {}

        with Session(engine) as session:
            rows = session.execute(
                sa_text("SELECT id, name, cron_expression, report_type, output_format, "
                        "parameters, recipients FROM report_schedules WHERE active = true")
            ).fetchall()

        for row in rows:
            try:
                parts = row.cron_expression.strip().split()
                if len(parts) != 5:
                    logger.warning("Invalid cron expression for schedule %s: %s",
                                   row.id, row.cron_expression)
                    continue

                minute, hour, day_of_month, month_of_year, day_of_week = parts

                entry_name = f"schedule-{row.id}"
                entries[entry_name] = {
                    "task": "reporting.run_scheduled_report",
                    "schedule": crontab(
                        minute=minute,
                        hour=hour,
                        day_of_month=day_of_month,
                        month_of_year=month_of_year,
                        day_of_week=day_of_week,
                    ),
                    "args": (row.id,),
                    "options": {"expires": 300},
                }

                logger.debug("Registered beat entry %s: %s (%s)",
                             entry_name, row.name, row.cron_expression)

            except Exception as exc:
                logger.error("Failed to parse schedule %s: %s", row.id, exc)

        # Update Celery app conf
        celery_app.conf.beat_schedule = entries
        logger.info("Synced %d schedule(s) to Celery Beat", len(entries))

    except Exception as exc:
        logger.error("Failed to sync beat schedules: %s", exc)


# ─── Manual Beat Schedule Refresh Task ───────────────────────────────────────

@celery_app.task(name="reporting.refresh_beat_schedules")
def refresh_beat_schedules() -> dict:
    """Manually refresh the Celery Beat schedule from the database.
    Call this from an API endpoint after creating/updating a schedule."""
    _sync_beat_schedules()
    count = len(celery_app.conf.beat_schedule or {})
    logger.info("Beat schedules refreshed: %d active", count)
    return {"status": "ok", "active_schedules": count}