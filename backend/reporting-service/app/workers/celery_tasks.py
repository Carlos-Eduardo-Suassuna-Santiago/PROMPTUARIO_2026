"""
Celery async workers for report generation.
Runs in a separate container (reporting-worker).
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from celery import Celery

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


@celery_app.task(bind=True, name="reporting.generate_report", max_retries=3)
def generate_report(self, job_id: str) -> dict:
    """Main Celery task: generate a report and upload to S3."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    engine = _get_sync_engine()
    logger.info("Generating report job: %s", job_id)

    with Session(engine) as session:
        # Load job
        job_row = session.execute(
            text("SELECT * FROM report_jobs WHERE id = :id"), {"id": job_id}
        ).fetchone()

        if not job_row:
            logger.error("Report job not found: %s", job_id)
            return {"error": "Job not found"}

        # Update status to RUNNING
        session.execute(
            text("UPDATE report_jobs SET status='RUNNING' WHERE id=:id"), {"id": job_id}
        )
        session.commit()

        try:
            params = job_row.parameters or {}
            report_type = job_row.report_type
            output_format = job_row.output_format

            data = _generate_data(session, report_type, params)
            s3_key = None
            row_count = len(data) if isinstance(data, list) else 1

            if output_format in ("CSV", "PDF"):
                s3_key = _upload_report(job_id, data, output_format, report_type)

            session.execute(
                text("""
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
            logger.info("Report job completed: %s (%d rows)", job_id, row_count)
            return {"job_id": job_id, "status": "COMPLETED", "rows": row_count}

        except Exception as e:
            logger.error("Report generation failed for %s: %s", job_id, e)
            session.execute(
                text("UPDATE report_jobs SET status='FAILED', error_message=:err WHERE id=:id"),
                {"err": str(e), "id": job_id},
            )
            session.commit()
            raise self.retry(exc=e, countdown=60)


def _generate_data(session, report_type: str, params: dict) -> list[dict]:
    """Generate report data from the reporting DB (pre-aggregated stats)."""
    from sqlalchemy import text

    from_date = params.get("from_date", "2024-01-01")
    to_date = params.get("to_date", datetime.now(timezone.utc).date().isoformat())

    if report_type == "CONSULTATIONS":
        rows = session.execute(
            text("""
                SELECT stat_date, value as consultations, metadata
                FROM daily_stats
                WHERE stat_type = 'CONSULTATIONS'
                  AND stat_date BETWEEN :from_date AND :to_date
                ORDER BY stat_date DESC
            """),
            {"from_date": from_date, "to_date": to_date},
        ).fetchall()
        return [{"date": r.stat_date, "consultations": r.consultations} for r in rows]

    elif report_type == "PATIENTS":
        rows = session.execute(
            text("""
                SELECT stat_date, value as new_patients
                FROM daily_stats
                WHERE stat_type = 'NEW_PATIENTS'
                  AND stat_date BETWEEN :from_date AND :to_date
                ORDER BY stat_date DESC
            """),
            {"from_date": from_date, "to_date": to_date},
        ).fetchall()
        return [{"date": r.stat_date, "new_patients": r.new_patients} for r in rows]

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
        rows = session.execute(text(q + " ORDER BY stat_date DESC"), bind).fetchall()
        return [{"doctor_id": r.doctor_id, "date": r.stat_date, "consultations": r.consultations} for r in rows]

    return []


def _upload_report(job_id: str, data: list, output_format: str, report_type: str) -> str:
    s3 = _get_s3()
    _ensure_bucket(s3, settings.S3_BUCKET_REPORTS)
    key = f"reports/{report_type.lower()}/{job_id}.{output_format.lower()}"

    if output_format == "CSV":
        if not data:
            content = b""
        else:
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
            content = buf.getvalue().encode("utf-8-sig")  # BOM for Excel

        s3.put_object(
            Bucket=settings.S3_BUCKET_REPORTS,
            Key=key,
            Body=content,
            ContentType="text/csv",
        )

    elif output_format == "PDF":
        # Simple HTML → PDF via weasyprint
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
