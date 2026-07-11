# Backup operacional e restauração do PROMPTUÁRIO

## Visão geral

O fluxo operacional de backup do PROMPTUÁRIO foi implementado como um serviço dedicado chamado `backup-service`.
Ele executa:
- backup dos bancos PostgreSQL `iam_db`, `patient_db`, `clinical_db` e `reporting_db`;
- backup do banco MongoDB `ai_db`;
- persistência local em `/var/backups`;
- upload para MinIO no bucket `backups`;
- registro do último status em `status.json`.

## Configuração

Variáveis principais no `docker-compose.yml`:
- `BACKUP_SCHEDULE_HOURS`: periodicidade do agendamento (padrão `24`)
- `BACKUP_RETENTION_DAYS`: retenção em dias (padrão `7`)
- `MINIO_BACKUP_BUCKET`: bucket de destino (padrão `backups`)
- `BACKUP_ROOT_DIR`: volume local de backup (padrão `/var/backups`)

## Execução

### Manual

```bash
cd backend
make backup-once
```

### Agendada

```bash
cd backend
make backup
```

## Restore

### PostgreSQL

```bash
cd backend
make restore-db FILE=/var/backups/postgresql/iam_db/2026/07/11/postgres_iam_db_20260711_120000.sql.gz TARGET=iam_db
```

### MongoDB

```bash
cd backend
make restore-mongo FILE=/var/backups/mongodb/ai_db/2026/07/11/mongo_ai_db_20260711_120000.archive.gz TARGET=ai_db
```

## Verificação

```bash
cd backend
make status
docker compose logs backup-service --tail=100
```

## Considerações operacionais

- Um backup individual que falhe não derruba os demais bancos nem os serviços principais.
- O status final é sempre registrado em `status.json` para inspeção rápida.
- O volume `/var/backups` deve ser montado em um storage persistente em ambientes reais.
