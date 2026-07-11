"""
PROMPTUÁRIO — Backup Service

Executa backup dos bancos PostgreSQL e MongoDB e envia artefatos para MinIO (S3)
com persistência local em volume compartilhado. O serviço pode ser executado
manualmente ou agendado via cron/compose.
"""
from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import boto3
import schedule
from botocore.exceptions import ClientError, EndpointConnectionError

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("backup_runner")

# ── Configuração via variáveis de ambiente ────────────────────────────────

POSTGRES_DATABASES = [
    {"host": "db-iam", "user": "iam", "password": "iam_pass", "dbname": "iam_db"},
    {"host": "db-patient", "user": "patient", "password": "patient_pass", "dbname": "patient_db"},
    {"host": "db-clinical", "user": "clinical", "password": "clinical_pass", "dbname": "clinical_db"},
    {"host": "db-reporting", "user": "reporting", "password": "reporting_pass", "dbname": "reporting_db"},
]

MONGO_CONFIG = {
    "host": os.getenv("MONGO_HOST", "db-ai"),
    "user": os.getenv("MONGO_USER", "ai"),
    "password": os.getenv("MONGO_PASS", "ai_pass"),
    "dbname": os.getenv("MONGO_DB", "ai_db"),
}

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "promptuario")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "promptuario_pass")
BACKUP_BUCKET = os.getenv("MINIO_BACKUP_BUCKET", "backups")
RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "7"))
SCHEDULE_HOURS = int(os.getenv("BACKUP_SCHEDULE_HOURS", "24"))
BACKUP_ROOT_DIR = Path(os.getenv("BACKUP_ROOT_DIR", "/var/backups"))
STATUS_FILE = BACKUP_ROOT_DIR / "status.json"

# ── Logging para arquivo persistente ──────────────────────────────────────

BACKUP_ROOT_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = BACKUP_ROOT_DIR / "backup.log"
if not logger.handlers:
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(file_handler)

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
    except (ClientError, EndpointConnectionError):
        try:
            s3.create_bucket(Bucket=BACKUP_BUCKET)
            logger.info("Bucket '%s' criado.", BACKUP_BUCKET)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Não foi possível criar o bucket '%s': %s", BACKUP_BUCKET, exc)


def upload_to_s3(local_path: Path, kind: str, dbname: str) -> str | None:
    """Upload do artefato para MinIO mantendo cópia local persistente."""
    s3 = get_s3_client()
    today = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    key = f"backups/{kind}/{dbname}/{today}/{local_path.name}"
    try:
        s3.upload_file(str(local_path), BACKUP_BUCKET, key)
        logger.info("Upload concluído: s3://%s/%s", BACKUP_BUCKET, key)
        return key
    except Exception as exc:
        logger.error("Falha no upload de %s: %s", local_path.name, exc)
        return None


def write_status_report(results: list[dict[str, Any]], status: str, mode: str) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "status": status,
        "backups": results,
    }
    STATUS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Status do backup salvo em %s", STATUS_FILE)


def _build_backup_path(kind: str, dbname: str, filename: str) -> Path:
    ts = datetime.now(timezone.utc)
    folder = BACKUP_ROOT_DIR / kind / dbname / f"{ts:%Y}" / f"{ts:%m}" / f"{ts:%d}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / filename


def backup_postgres(cfg: dict[str, str], mode: str) -> dict[str, Any]:
    """pg_dump comprimido com gzip. Retorna um registro de status."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"postgres_{cfg['dbname']}_{ts}.sql.gz"
    filepath = _build_backup_path("postgresql", cfg["dbname"], filename)
    env = {**os.environ, "PGPASSWORD": cfg["password"]}
    t0 = time.time()

    try:
        dump = subprocess.run(
            ["pg_dump", "-h", cfg["host"], "-U", cfg["user"], cfg["dbname"]],
            capture_output=True,
            env=env,
            timeout=600,
        )
        if dump.returncode != 0:
            error_text = dump.stderr.decode("utf-8", errors="replace")[:500]
            logger.error("pg_dump falhou para %s: %s", cfg["dbname"], error_text)
            return {"database": cfg["dbname"], "kind": "postgres", "status": "failed", "error": error_text}

        with gzip.open(filepath, "wb") as handle:
            handle.write(dump.stdout)

        size_mb = filepath.stat().st_size / 1_048_576
        elapsed = time.time() - t0
        key = upload_to_s3(filepath, "postgresql", cfg["dbname"])
        logger.info("Backup PostgreSQL %s: %.2f MB em %.1fs → %s", cfg["dbname"], size_mb, elapsed, filepath.name)
        return {
            "database": cfg["dbname"],
            "kind": "postgres",
            "status": "uploaded" if key else "local_only",
            "path": str(filepath),
            "s3_key": key,
            "size_mb": round(size_mb, 2),
            "mode": mode,
        }
    except subprocess.TimeoutExpired:
        logger.error("Timeout ao fazer backup de %s (>10min)", cfg["dbname"])
        return {"database": cfg["dbname"], "kind": "postgres", "status": "failed", "error": "timeout"}
    except Exception as exc:
        logger.error("Erro ao fazer backup de %s: %s", cfg["dbname"], exc)
        return {"database": cfg["dbname"], "kind": "postgres", "status": "failed", "error": str(exc)}


def backup_mongo(cfg: dict[str, str], mode: str) -> dict[str, Any]:
    """mongodump comprimido. Retorna um registro de status."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"mongo_{cfg['dbname']}_{ts}.archive.gz"
    filepath = _build_backup_path("mongodb", cfg["dbname"], filename)
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
            error_text = result.stderr.decode("utf-8", errors="replace")[:500]
            logger.error("mongodump falhou: %s", error_text)
            return {"database": cfg["dbname"], "kind": "mongo", "status": "failed", "error": error_text}

        size_mb = filepath.stat().st_size / 1_048_576
        elapsed = time.time() - t0
        key = upload_to_s3(filepath, "mongodb", cfg["dbname"])
        logger.info("Backup MongoDB %s: %.2f MB em %.1fs → %s", cfg["dbname"], size_mb, elapsed, filepath.name)
        return {
            "database": cfg["dbname"],
            "kind": "mongo",
            "status": "uploaded" if key else "local_only",
            "path": str(filepath),
            "s3_key": key,
            "size_mb": round(size_mb, 2),
            "mode": mode,
        }
    except subprocess.TimeoutExpired:
        logger.error("Timeout ao fazer backup MongoDB (>10min)")
        return {"database": cfg["dbname"], "kind": "mongo", "status": "failed", "error": "timeout"}
    except Exception as exc:
        logger.error("Erro ao fazer backup MongoDB: %s", exc)
        return {"database": cfg["dbname"], "kind": "mongo", "status": "failed", "error": str(exc)}


def cleanup_old_backups() -> int:
    """Remove artefatos antigos do MinIO e do volume local conforme a retenção."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    removed = 0

    # Limpeza local
    try:
        for path in BACKUP_ROOT_DIR.rglob("*"):
            if path.is_file() and path.stat().st_mtime < cutoff.timestamp():
                path.unlink(missing_ok=True)
                removed += 1
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Falha ao limpar artefatos locais: %s", exc)

    # Limpeza no MinIO
    try:
        s3 = get_s3_client()
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=BACKUP_BUCKET):
            for obj in page.get("Contents", []):
                if obj["LastModified"] < cutoff:
                    s3.delete_object(Bucket=BACKUP_BUCKET, Key=obj["Key"])
                    removed += 1
    except Exception as exc:
        logger.warning("Falha na limpeza de backups do MinIO: %s", exc)

    if removed:
        logger.info("Limpeza concluída: %d artefato(s) removido(s).", removed)
    return removed


def restore_postgres(cfg: dict[str, str], backup_path: Path) -> bool:
    """Restaura um dump PostgreSQL a partir de um arquivo local."""
    if not backup_path.exists():
        logger.error("Arquivo de backup não encontrado: %s", backup_path)
        return False

    env = {**os.environ, "PGPASSWORD": cfg["password"]}
    try:
        command = ["sh", "-c", f"gzip -dc {backup_path} | psql -h {cfg['host']} -U {cfg['user']} {cfg['dbname']}"]
        subprocess.run(command, check=True, env=env, timeout=1800, capture_output=True)
        logger.info("Restore PostgreSQL concluído com sucesso: %s", backup_path)
        return True
    except subprocess.CalledProcessError as exc:
        logger.error("Restore PostgreSQL falhou: %s", exc.stderr.decode("utf-8", errors="replace")[:500])
        return False
    except Exception as exc:
        logger.error("Erro inesperado no restore PostgreSQL: %s", exc)
        return False


def restore_mongo(cfg: dict[str, str], backup_path: Path) -> bool:
    """Restaura um dump MongoDB a partir de um arquivo local."""
    if not backup_path.exists():
        logger.error("Arquivo de backup não encontrado: %s", backup_path)
        return False

    try:
        command = [
            "mongorestore",
            f"--host={cfg['host']}",
            f"--username={cfg['user']}",
            f"--password={cfg['password']}",
            "--authenticationDatabase=admin",
            f"--db={cfg['dbname']}",
            "--gzip",
            f"--archive={str(backup_path)}",
        ]
        subprocess.run(command, check=True, timeout=1800, capture_output=True)
        logger.info("Restore MongoDB concluído com sucesso: %s", backup_path)
        return True
    except subprocess.CalledProcessError as exc:
        logger.error("Restore MongoDB falhou: %s", exc.stderr.decode("utf-8", errors="replace")[:500])
        return False
    except Exception as exc:
        logger.error("Erro inesperado no restore MongoDB: %s", exc)
        return False


def run_all_backups(mode: str = "scheduled") -> list[dict[str, Any]]:
    start = time.time()
    logger.info("════ Iniciando backup completo (%s) ════", mode)

    ensure_bucket()
    results: list[dict[str, Any]] = []

    for cfg in POSTGRES_DATABASES:
        results.append(backup_postgres(cfg, mode))

    results.append(backup_mongo(MONGO_CONFIG, mode))
    cleanup_old_backups()

    elapsed = time.time() - start
    status = "success" if all(item["status"] in {"uploaded", "local_only"} for item in results) else "partial"
    write_status_report(results, status, mode)
    logger.info("════ Backup concluído em %.1fs: %s ════", elapsed, json.dumps(results))
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backup operacional do PROMPTUÁRIO")
    parser.add_argument("--once", action="store_true", help="Executa um backup único e encerra")
    parser.add_argument("--restore", action="store_true", help="Executa um restore controlado")
    parser.add_argument("--kind", choices=["postgres", "mongo"], help="Tipo de restore")
    parser.add_argument("--target", help="Nome do banco alvo (ex.: iam_db ou ai_db)")
    parser.add_argument("--file", help="Caminho do arquivo local de backup para restore")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.restore:
        if not args.kind or not args.file:
            logger.error("Use --kind e --file para restaurar")
            return 2

        if args.kind == "postgres":
            target_cfg = next((cfg for cfg in POSTGRES_DATABASES if cfg["dbname"] == args.target or not args.target), None)
            if not target_cfg:
                logger.error("Banco PostgreSQL não encontrado: %s", args.target)
                return 2
            success = restore_postgres(target_cfg, Path(args.file))
            return 0 if success else 1

        target_cfg = MONGO_CONFIG.copy()
        if args.target and args.target != target_cfg["dbname"]:
            target_cfg["dbname"] = args.target
        success = restore_mongo(target_cfg, Path(args.file))
        return 0 if success else 1

    logger.info("Backup service iniciado (agendamento: cada %dh, retenção: %dd, volume: %s)", SCHEDULE_HOURS, RETENTION_DAYS, BACKUP_ROOT_DIR)
    if args.once:
        run_all_backups(mode="manual")
        return 0

    run_all_backups()
    schedule.every(SCHEDULE_HOURS).hours.do(run_all_backups, mode="scheduled")
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    sys.exit(main())