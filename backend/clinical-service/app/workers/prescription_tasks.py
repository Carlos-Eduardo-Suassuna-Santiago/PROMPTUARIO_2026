"""
Celery task para geração assíncrona de PDF de prescrições.

Fluxo:
  1. PrescriptionService.create() salva a prescrição e commita
  2. Chama generate_prescription_pdf.delay() logo após o commit
  3. Gera HTML -> PDF via WeasyPrint
  4. Faz upload para MinIO
  5. Atualiza pdf_s3_key na tabela prescriptions via psycopg2 síncrono
"""
from __future__ import annotations

import logging
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from app.config import settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_s3():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )


def _ensure_bucket(s3_client) -> None:
    try:
        s3_client.head_bucket(Bucket=settings.S3_BUCKET_PRESCRIPTIONS)
    except ClientError:
        s3_client.create_bucket(Bucket=settings.S3_BUCKET_PRESCRIPTIONS)


def _get_sync_db_url() -> str:
    """Converte URL asyncpg para psycopg2 (Celery é síncrono)."""
    return settings.DATABASE_URL.replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://"
    )


def _build_prescription_html(
    patient_name: str,
    doctor_name: str,
    medications: list[dict],
    instructions: str | None,
    valid_days: int,
    prescription_id: str,
) -> str:
    """Gera HTML da prescrição para conversão em PDF."""
    med_items = "".join(
        f"""<li>
            <strong>{m.get('name', '')} {m.get('dosage', '')}</strong><br>
            {m.get('frequency', '')} por {m.get('duration_days', 7)} dias
            {'<br><em>' + m.get('instructions', '') + '</em>' if m.get('instructions') else ''}
        </li>"""
        for m in medications
    )

    instructions_html = (
        f"<p><strong>Instruções gerais:</strong> {instructions}</p>"
        if instructions
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: 'Arial', sans-serif; margin: 40px; color: #333; }}
        h1 {{ color: #1a6e6e; border-bottom: 2px solid #1a6e6e; padding-bottom: 8px; font-size: 22px; }}
        .header {{ margin-bottom: 24px; }}
        .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 24px; }}
        .info-item .label {{ font-size: 11px; color: #888; text-transform: uppercase; margin-bottom: 2px; }}
        .info-item .value {{ font-size: 14px; font-weight: bold; }}
        h2 {{ font-size: 16px; color: #333; margin-top: 24px; }}
        ul {{ list-style: none; padding: 0; }}
        ul li {{ padding: 10px; margin-bottom: 8px; background: #f9f9f9; border-left: 3px solid #1a6e6e; border-radius: 4px; }}
        .footer {{ margin-top: 40px; padding-top: 12px; border-top: 1px solid #eee; font-size: 11px; color: #aaa; }}
    </style>
</head>
<body>
    <h1>Prescrição Médica</h1>
    <div class="info-grid">
        <div class="info-item">
            <div class="label">Paciente</div>
            <div class="value">{patient_name}</div>
        </div>
        <div class="info-item">
            <div class="label">Médico Responsável</div>
            <div class="value">{doctor_name}</div>
        </div>
        <div class="info-item">
            <div class="label">Data de Emissão</div>
            <div class="value">{datetime.now().strftime('%d/%m/%Y')}</div>
        </div>
        <div class="info-item">
            <div class="label">Válida por</div>
            <div class="value">{valid_days} dias</div>
        </div>
    </div>
    <h2>Medicamentos Prescritos</h2>
    <ul>{med_items}</ul>
    {instructions_html}
    <div class="footer">
        Documento gerado eletronicamente · PROMPTUÁRIO EHR · ID: {prescription_id}
    </div>
</body>
</html>"""


@celery_app.task(
    bind=True,
    name="clinical.generate_prescription_pdf",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
)
def generate_prescription_pdf(
    self,
    prescription_id: str,
    patient_name: str,
    doctor_name: str,
    medications: list[dict],
    instructions: str | None,
    valid_days: int,
) -> dict:
    """
    Gera PDF da prescrição e faz upload para MinIO.
    Atualiza o campo pdf_s3_key na tabela prescriptions.
    """
    logger.info("Gerando PDF para prescrição %s", prescription_id)

    try:
        from weasyprint import HTML

        # 1. Gera HTML e converte para PDF
        html_content = _build_prescription_html(
            patient_name=patient_name,
            doctor_name=doctor_name,
            medications=medications,
            instructions=instructions,
            valid_days=valid_days,
            prescription_id=prescription_id,
        )
        pdf_bytes = HTML(string=html_content).write_pdf()

        # 2. Upload para MinIO
        s3 = _get_s3()
        _ensure_bucket(s3)

        year = datetime.now().year
        s3_key = f"prescriptions/{year}/{prescription_id}.pdf"

        s3.put_object(
            Bucket=settings.S3_BUCKET_PRESCRIPTIONS,
            Key=s3_key,
            Body=pdf_bytes,
            ContentType="application/pdf",
        )
        logger.info("PDF uploaded: s3://%s/%s", settings.S3_BUCKET_PRESCRIPTIONS, s3_key)

        # 3. Atualiza pdf_s3_key no banco via psycopg2 síncrono
        import psycopg2
        dsn = _get_sync_db_url()

        conn = psycopg2.connect(dsn)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE prescriptions SET pdf_s3_key = %s WHERE id = %s",
                    (s3_key, prescription_id),
                )
            conn.commit()
            logger.info("pdf_s3_key atualizado para prescrição %s", prescription_id)
        finally:
            conn.close()

        return {"prescription_id": prescription_id, "s3_key": s3_key, "status": "ok"}

    except Exception as exc:
        logger.error("Erro ao gerar PDF para %s: %s", prescription_id, exc)
        raise self.retry(exc=exc)