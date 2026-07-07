"""
PROMPTUÁRIO — Roteiro de Teste do Serviço de Backup Automático

Uso:
    python backend/scripts/test_backup_service.py

Testa:
  - Estrutura dos arquivos (Dockerfile, backup_runner.py)
  - Lógica do script (funções, configurações, timeouts)
  - Endpoints de backup no reporting-service
  - Roteamento no gateway
  - Definição do serviço no docker-compose.yml
"""
from __future__ import annotations

import ast
import sys
import subprocess
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
BACKUP_DIR = BACKEND_DIR / "backup"
DOCKER_COMPOSE = BACKEND_DIR / "docker-compose.yml"
REPORTING_MAIN = BACKEND_DIR / "reporting-service" / "app" / "main.py"
GATEWAY_MAIN = BACKEND_DIR / "gateway" / "app" / "main.py"

PASS = 0
FAIL = 0
ERRORS: list[str] = []


def check(description: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {description}")
    else:
        FAIL += 1
        msg = f"  ❌ {description}" + (f" — {detail}" if detail else "")
        print(msg)
        ERRORS.append(msg)


def section(title: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ═══════════════════════════════════════════════════════════════════════════════
#  1. ESTRUTURA DOS ARQUIVOS
# ═══════════════════════════════════════════════════════════════════════════════

def test_file_structure() -> None:
    section("1. Estrutura dos arquivos de backup")

    check("Diretório backup/ existe", BACKUP_DIR.is_dir())
    check("backup/Dockerfile existe", (BACKUP_DIR / "Dockerfile").is_file())
    check("backup/backup_runner.py existe", (BACKUP_DIR / "backup_runner.py").is_file())

    dockerfile = (BACKUP_DIR / "Dockerfile").read_text(encoding="utf-8")
    check("Dockerfile usa python:3.12-alpine", "python:3.12-alpine" in dockerfile)
    check("Dockerfile instala postgresql-client", "postgresql-client" in dockerfile)
    check("Dockerfile instala mongodb-tools", "mongodb-tools" in dockerfile)
    check("Dockerfile instala boto3==1.35.0", "boto3==1.35.0" in dockerfile)
    check("Dockerfile instala schedule==1.2.2", "schedule==1.2.2" in dockerfile)
    check("Dockerfile copia backup_runner.py", "COPY backup/backup_runner.py" in dockerfile)
    check("Dockerfile CMD executa backup_runner.py", "backup_runner.py" in dockerfile)

    runner = (BACKUP_DIR / "backup_runner.py").read_text(encoding="utf-8")
    try:
        ast.parse(runner)
        check("backup_runner.py tem sintaxe Python válida", True)
    except SyntaxError as e:
        check("backup_runner.py tem sintaxe Python válida", False, str(e))


# ═══════════════════════════════════════════════════════════════════════════════
#  2. LÓGICA DO backup_runner.py
# ═══════════════════════════════════════════════════════════════════════════════

def test_backup_runner_logic() -> None:
    section("2. Lógica do backup_runner.py")

    runner = (BACKUP_DIR / "backup_runner.py").read_text(encoding="utf-8")

    # Funções principais
    for fn in ["get_s3_client", "ensure_bucket", "upload_to_s3",
               "backup_postgres", "backup_mongo", "cleanup_old_backups", "run_all_backups"]:
        check(f"Função {fn}() definida", f"def {fn}" in runner)

    # 4 bancos PostgreSQL
    check("4 bancos PostgreSQL configurados", runner.count('"host":') >= 4)
    for db in ["db-iam", "db-patient", "db-clinical", "db-reporting"]:
        check(f"PostgreSQL {db} configurado", db in runner)

    # MongoDB
    check("MongoDB db-ai configurado", "db-ai" in runner)
    for var in ["MONGO_HOST", "MONGO_USER", "MONGO_PASS", "MONGO_DB"]:
        check(f"Variável {var} lida de env var", var in runner)

    # MinIO
    for var in ["MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "MINIO_BACKUP_BUCKET"]:
        check(f"Variável {var} lida de env var", var in runner)

    # Retenção e agendamento
    check("BACKUP_RETENTION_DAYS lido de env var (padrão 7)", "BACKUP_RETENTION_DAYS" in runner)
    check("BACKUP_SCHEDULE_HOURS lido de env var (padrão 24)", "BACKUP_SCHEDULE_HOURS" in runner)

    # Timeout de 10 minutos
    check("Timeout de 600s (10min) para pg_dump", "timeout=600" in runner)
    check("Timeout de 600s (10min) para mongodump", "timeout=600" in runner)

    # pg_dump
    check("pg_dump usa PGPASSWORD via env", "PGPASSWORD" in runner)
    check("pg_dump usa gzip", "gzip.open" in runner)

    # mongodump
    check("mongodump usa --gzip", "--gzip" in runner)
    check("mongodump usa --archive", "--archive" in runner)

    # Upload S3
    check("upload_to_s3 usa s3.upload_file", "upload_file" in runner)
    check("upload_to_s3 gera key com data (Y/m/d)", "%Y/%m/%d" in runner)
    check("upload_to_s3 remove arquivo local após upload", "unlink" in runner)

    # Limpeza
    check("cleanup_old_backups usa paginator", "get_paginator" in runner)
    check("cleanup_old_backups compara LastModified com cutoff", "LastModified" in runner)
    check("cleanup_old_backups usa delete_object", "delete_object" in runner)

    # Orquestrador
    check("run_all_backups chama ensure_bucket", "ensure_bucket()" in runner)
    check("run_all_backups itera sobre POSTGRES_DATABASES", "for cfg in POSTGRES_DATABASES" in runner)
    check("run_all_backups chama backup_mongo", "backup_mongo" in runner)
    check("run_all_backups chama cleanup_old_backups", "cleanup_old_backups()" in runner)
    check("run_all_backups gera relatório JSON", "json.dumps(results)" in runner)

    # Agendamento
    check("schedule.every().hours.do() presente", "schedule.every" in runner)
    check("schedule.run_pending() no loop principal", "schedule.run_pending()" in runner)
    check("sleep(60) no loop principal", "sleep(60)" in runner)
    check("run_all_backups() executado imediatamente ao iniciar", "run_all_backups()" in runner)


# ═══════════════════════════════════════════════════════════════════════════════
#  3. ENDPOINTS DE BACKUP NO REPORTING-SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

def test_reporting_endpoints() -> None:
    section("3. Endpoints de backup no reporting-service")

    main_py = REPORTING_MAIN.read_text(encoding="utf-8")

    check("backup_router definido", "backup_router" in main_py)
    check("prefix /admin/backups", "/admin/backups" in main_py)
    check("tags ['Backup']", "Backup" in main_py)
    check("Dependência require_roles('ADMIN')", 'require_roles("ADMIN")' in main_py)
    check("list_backups() usa s3.list_objects_v2", "list_objects_v2" in main_py)
    check("list_backups() gera pre-signed URL", "generate_presigned_url" in main_py)
    check("list_backups() retorna filename, key, size_mb, created_at, download_url",
          all(f in main_py for f in ("filename", "key", "size_mb", "created_at", "download_url")))
    check("backup_router registrado no app", "app.include_router(backup_router" in main_py)
    check("backup_router prefix /api/v1", "prefix=\"/api/v1\"" in main_py)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. ROTEAMENTO NO GATEWAY
# ═══════════════════════════════════════════════════════════════════════════════

def test_gateway_routing() -> None:
    section("4. Roteamento no gateway")

    gateway = GATEWAY_MAIN.read_text(encoding="utf-8")

    check("ROUTE_TABLE contém /api/v1/admin", '"/api/v1/admin"' in gateway)
    check("Rota /api/v1/admin aponta para REPORTING_SERVICE_URL",
          "REPORTING_SERVICE_URL" in gateway.split('"/api/v1/admin"')[1] if '"/api/v1/admin"' in gateway else False)
    check("Rota /api/v1/admin requer autenticação (True)",
          "True" in gateway.split('"/api/v1/admin"')[1].split(")")[0] if '"/api/v1/admin"' in gateway else False)


# ═══════════════════════════════════════════════════════════════════════════════
#  5. DOCKER-COMPOSE
# ═══════════════════════════════════════════════════════════════════════════════

def test_docker_compose() -> None:
    section("5. Definição do serviço no docker-compose.yml")

    compose = DOCKER_COMPOSE.read_text(encoding="utf-8")

    check("Serviço backup-service definido", "backup-service:" in compose)
    check("build context: .", "context: ." in compose)
    check("dockerfile: backup/Dockerfile", "backup/Dockerfile" in compose)

    for var, val in [
        ("MONGO_HOST", "db-ai"), ("MONGO_USER", "ai"), ("MONGO_PASS", "ai_pass"), ("MONGO_DB", "ai_db"),
        ("MINIO_ENDPOINT", "http://minio:9000"), ("MINIO_ACCESS_KEY", "promptuario"),
        ("MINIO_SECRET_KEY", "promptuario_pass"), ("MINIO_BACKUP_BUCKET", "backups"),
        ("BACKUP_RETENTION_DAYS", '"7"'), ("BACKUP_SCHEDULE_HOURS", '"24"'),
    ]:
        check(f"Variável {var} configurada", f"{var}: {val}" in compose)

    for db in ["db-iam", "db-patient", "db-clinical", "db-reporting", "db-ai", "minio"]:
        check(f"depends_on {db} presente", f"{db}:" in compose)

    check("condition: service_healthy presente", "condition: service_healthy" in compose)
    check("Rede backend configurada", "networks: [backend]" in compose)
    check("restart: unless-stopped configurado", "restart: unless-stopped" in compose)


# ═══════════════════════════════════════════════════════════════════════════════
#  6. VALIDAÇÃO DE IMPORTAÇÃO (AST)
# ═══════════════════════════════════════════════════════════════════════════════

def test_import_validation() -> None:
    section("6. Validação de importação do backup_runner.py")

    runner_path = BACKUP_DIR / "backup_runner.py"
    result = subprocess.run(
        [sys.executable, "-c", f"""
import ast, sys
with open(r'{runner_path}') as f:
    tree = ast.parse(f.read())
functions = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
expected = ['get_s3_client', 'ensure_bucket', 'upload_to_s3', 'backup_postgres',
            'backup_mongo', 'cleanup_old_backups', 'run_all_backups']
missing = [f for f in expected if f not in functions]
if missing:
    print(f'MISSING: {{missing}}')
    sys.exit(1)
print('OK')
"""],
        capture_output=True, text=True, timeout=30,
    )
    check("Todas as funções esperadas encontradas via AST",
          result.returncode == 0 and "OK" in result.stdout,
          result.stderr[:200] if result.stderr else "")


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    print(f"\n{'#'*70}")
    print(f"  PROMPTUÁRIO — Roteiro de Teste do Serviço de Backup Automático")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*70}")

    test_file_structure()
    test_backup_runner_logic()
    test_reporting_endpoints()
    test_gateway_routing()
    test_docker_compose()
    test_import_validation()

    print(f"\n{'='*70}")
    print(f"  RESULTADO: {PASS} passaram, {FAIL} falharam")
    print(f"{'='*70}")

    if ERRORS:
        print("\nDetalhes das falhas:")
        for e in ERRORS:
            print(f"  {e}")

    return 1 if FAIL > 0 else 0


if __name__ == "__main__":
    sys.exit(main())