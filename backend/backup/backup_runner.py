"""
PROMPTUÁRIO — Backup Service

Executa backup de todos os bancos de dados e envia para MinIO (S3).
Agenda: a cada BACKUP_SCHEDULE_HOURS horas (padrão: 24h).
Retenção: BACKUP_RETENTION_DAYS dias (padrão: 7).
"""
from __future__ import annotations

import gzip
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
import schedule
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── Configuração via variáveis de ambiente ────────────────────────────────

POSTGRES_DATABASES = [
    {"host": "db-iam",       "user": "iam",       "password": "iam_pass",       "dbname": "iam_db"},
    {"host": "db-patient",   "user": "patient",   "password": "patient_pass",   "dbname": "patient_db"},
    {"host": "db-clinical",  "user": "clinical",  "password": "clinical_pass",  "dbname": "clinical_db"},
    {"host": "db-reporting", "user": "reporting", "password": "reporting_pass", "dbname": "reporting_db"},
]

MONGO_CONFIG = {
    "host":     os.getenv("MONGO_HOST",     "db-ai"),
    "user":     os.getenv("MONGO_USER",     "ai"),
    "password": os.getenv("MONGO_PASS",     "ai_pass"),
    "dbname":   os.getenv("MONGO_DB",       "ai_db"),
}

MINIO_ENDPOINT       = os.getenv("MINIO_ENDPOINT",      "http://minio:9000")
MINIO_ACCESS_KEY     = os.getenv("MINIO_ACCESS_KEY",    "promptuario")
MINIO_SECRET_KEY     = os.getenv("MINIO_SECRET_KEY",    "promptuario_pass")
BACKUP_BUCKET        = os.getenv("MINIO_BACKUP_BUCKET", "backups")
RETENTION_DAYS       = int(os.getenv("BACKUP_RETENTION_DAYS",  "7"))
SCHEDULE_HOURS       = int(os.getenv("BACKUP_SCHEDULE_HOURS",  "24"))

BACKUP_DIR = Path("/tmp/backups")

# ── S3 / MinIO ────────────────────────────────────────────────────────────

def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    )

def ensure_bucket() -> None:
    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=BACKUP_BUCKET)
    except ClientError:
        s3.create_bucket(Bucket=BACKUP_BUCKET)
        logger.info("Bucket '%s' criado.", BACKUP_BUCKET)

def upload_to_s3(local_path: Path) -> str | None:
    """Upload arquivo para MinIO. Retorna a S3 key ou None em caso de erro."""
    s3 = get_s3_client()
    today = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    key = f"backups/{today}/{local_path.name}"
    try:
        s3.upload_file(str(local_path), BACKUP_BUCKET, key)
        logger.info("Upload concluído: s3://%s/%s", BACKUP_BUCKET, key)
        local_path.unlink(missing_ok=True)
        return key
    except Exception as exc:
        logger.error("Falha no upload de %s: %s", local_path.name, exc)
        return None

# ── PostgreSQL ────────────────────────────────────────────────────────────

def backup_postgres(cfg: dict) -> Path | None:
    """pg_dump comprimido com gzip. Retorna o path local ou None."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"postgres_{cfg['dbname']}_{ts}.sql.gz"
    filepath = BACKUP_DIR / filename
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    env = {**os.environ, "PGPASSWORD": cfg["password"]}
    t0 = time.time()
    
    try:
        dump = subprocess.run(
            ["pg_dump", "-h", cfg["host"], "-U", cfg["user"], cfg["dbname"]],
            capture_output=True,
            env=env,
            timeout=600,   # 10 minutos máximo
        )
        if dump.returncode != 0:
            logger.error(
                "pg_dump falhou para %s: %s",
                cfg["dbname"],
                dump.stderr.decode("utf-8", errors="replace")[:500],
            )
            return None
        
        with gzip.open(filepath, "wb") as f:
            f.write(dump.stdout)
        
        size_mb = filepath.stat().st_size / 1_048_576
        elapsed = time.time() - t0
        logger.info(
            "Backup PostgreSQL %s: %.2f MB em %.1fs → %s",
            cfg["dbname"], size_mb, elapsed, filename,
        )
        return filepath
    
    except subprocess.TimeoutExpired:
        logger.error("Timeout ao fazer backup de %s (>10min)", cfg["dbname"])
        return None
    except Exception as exc:
        logger.error("Erro ao fazer backup de %s: %s", cfg["dbname"], exc)
        return None

# ── MongoDB ───────────────────────────────────────────────────────────────

def backup_mongo(cfg: dict) -> Path | None:
    """mongodump comprimido. Retorna o path local ou None."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"mongo_{cfg['dbname']}_{ts}.gz"
    filepath = BACKUP_DIR / filename
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    t0 = time.time()
    try:
        result = subprocess.run(
            [
                "mongodump",
                f"--host={cfg['host']}",
                f"--username={cfg['user']}",
                f"--password={cfg['password']}",
                "--authenticationDatabase=admin",
                f"--db={cfg['dbname']}",
                "--gzip",
                f"--archive={str(filepath)}",
            ],
            capture_output=True,
            timeout=600,
        )
        if result.returncode != 0:
            logger.error(
                "mongodump falhou: %s",
                result.stderr.decode("utf-8", errors="replace")[:500],
            )
            return None
        
        size_mb = filepath.stat().st_size / 1_048_576
        elapsed = time.time() - t0
        logger.info(
            "Backup MongoDB %s: %.2f MB em %.1fs → %s",
            cfg["dbname"], size_mb, elapsed, filename,
        )
        return filepath
    
    except subprocess.TimeoutExpired:
        logger.error("Timeout ao fazer backup MongoDB (>10min)")
        return None
    except Exception as exc:
        logger.error("Erro ao fazer backup MongoDB: %s", exc)
        return None

# ── Limpeza de backups antigos ────────────────────────────────────────────

def cleanup_old_backups() -> int:
    """Remove backups mais antigos que RETENTION_DAYS. Retorna quantos foram removidos."""
    s3 = get_s3_client()
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    removed = 0
    try:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=BACKUP_BUCKET):
            for obj in page.get("Contents", []):
                if obj["LastModified"] < cutoff:
                    s3.delete_object(Bucket=BACKUP_BUCKET, Key=obj["Key"])
                    removed += 1
        if removed:
            logger.info("Limpeza: %d backup(s) antigos removidos.", removed)
        return removed
    except Exception as exc:
        logger.error("Erro na limpeza de backups: %s", exc)
        return 0

# ── Orquestrador ──────────────────────────────────────────────────────────

def run_all_backups() -> None:
    start = time.time()
    logger.info("════ Iniciando backup completo ════")
    
    ensure_bucket()
    results: dict[str, str] = {}
    
    # PostgreSQL
    for cfg in POSTGRES_DATABASES:
        filepath = backup_postgres(cfg)
        if filepath:
            key = upload_to_s3(filepath)
            results[cfg["dbname"]] = key if key else "upload_failed"
        else:
            results[cfg["dbname"]] = "backup_failed"
    
    # MongoDB
    filepath = backup_mongo(MONGO_CONFIG)
    if filepath:
        key = upload_to_s3(filepath)
        results[MONGO_CONFIG["dbname"]] = key if key else "upload_failed"
    else:
        results[MONGO_CONFIG["dbname"]] = "backup_failed"
    
    # Limpeza
    cleanup_old_backups()
    
    elapsed = time.time() - start
    successes = sum(1 for v in results.values() if v not in ("backup_failed", "upload_failed"))
    logger.info(
        "════ Backup concluído em %.1fs: %d/%d ok — %s ════",
        elapsed, successes, len(results), json.dumps(results),
    )

# ── Entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Backup service iniciado (agendamento: cada %dh, retenção: %dd)", 
                SCHEDULE_HOURS, RETENTION_DAYS)
    
    # Executa imediatamente ao iniciar
    run_all_backups()
    
    # Agenda execuções futuras
    schedule.every(SCHEDULE_HOURS).hours.do(run_all_backups)
    
    while True:
        schedule.run_pending()
        time.sleep(60)