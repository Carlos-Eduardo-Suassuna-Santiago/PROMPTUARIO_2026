# Auditoria, Monitoramento e Backup

## 4.1 Auditoria de Banco de Dados

O sistema registra eventos de auditoria (audit logs) para operações sensíveis e autenticações. Logs são imutáveis e armazenados para análise e conformidade.

O que é auditado (exemplos por serviço):
| Serviço | Operações auditadas | Tabela de logs |
|---|---|---|
| IAM | AUTH_LOGIN, AUTH_LOGIN_FAILED, AUTH_LOGOUT, INSERT/UPDATE/DELETE em `users`, PASSWORD_CHANGE | `audit_logs` |
| Patient | INSERT/UPDATE/DELETE em `patients`, INSERT/DELETE em `allergies` | `audit_logs` |
| Clinical | INSERT em `appointments`, UPDATE (cancelamento), INSERT em `medical_records` / `prescriptions` | `audit_logs` |

Estrutura da tabela `audit_logs`:
- `id` (UUID / varchar): identificador do log
- `service` (varchar): serviço que gerou o evento (iam/patient/clinical/...)
- `operation` (varchar): operação auditada (AUTH_LOGIN, PATIENT_CREATE, etc.)
- `user_id` (varchar | null): id do usuário que disparou a ação
- `resource_id` (varchar | null): id do recurso afetado (patient_id, record_id)
- `details` (jsonb): payload descritivo (campos alterados, before/after)
- `timestamp` (timestamptz): data/hora do evento (UTC)
- `request_id` (varchar | null): correlação com request/tracing
- `ip_address` (varchar | null): IP de origem
- `immutable` (boolean): flag de controle (sempre true)
- `metadata` (jsonb | null): campos adicionais (user-agent, client_id)

Como consultar logs de auditoria:
```
GET /api/v1/audit/logs?service=iam&operation=AUTH_LOGIN&from_date=2026-01-01
Authorization: Bearer <token-admin>
```
Exemplo de resposta (JSON):
{
  "items": [
    {
      "id": "a1b2c3d4",
      "service": "iam",
      "operation": "AUTH_LOGIN",
      "user_id": "usr_123",
      "resource_id": null,
      "details": {"success": true},
      "timestamp": "2026-06-05T12:34:56Z",
      "request_id": "req_abc",
      "ip_address": "192.0.2.10"
    }
  ],
  "total": 1
}

Exportar logs:
- Iniciar exportação:
```
POST /api/v1/audit/export
Body: {"service": "all", "format": "CSV"}
```
- Após processamento, baixar:
```
GET /api/v1/reports/export/{job_id}/download
```

Detecção de atividades suspeitas:
```
GET /api/v1/audit/suspicious
```
Regras (exemplos): > 10 DELETEs/hora por conta; > 5 logins falhos em 7 dias — retorna lista de anomalias com evidências.

## 4.2 Monitoramento

URLs:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001 (admin/admin)
- Jaeger: http://localhost:16686
- RabbitMQ Management: http://localhost:15672 (promptuario / promptuario_pass)

Métricas coletadas (por serviço):
- `http_requests_total{service,method,endpoint,status_code}`
- `http_request_duration_seconds{service,method,endpoint}` (histograma)
- `celery_tasks_total{queue,status}`
- `db_connections{service}`

Alertas (exemplos em alerts.yml):
- ServiceDown: serviço down > 1 min → CRITICAL
- HighErrorRate: 5xx > 5% por 2min → WARNING
- HighLatency: P95 > 2s por 5min → WARNING

Como acessar traces no Jaeger:
1. Abra http://localhost:16686
2. Selecione o serviço no dropdown
3. Clique em "Find Traces"
4. Clique em um trace para ver spans e timings

Dashboard Grafana:
1. Abra http://localhost:3001 (admin/admin)
2. Dashboards → PROMPTUÁRIO → Observabilidade
3. Painéis: requests/s, taxa de erro, latência P95, health dos serviços, filas Celery

## 4.3 Backup

Frequência: diária (configurável via `BACKUP_SCHEDULE_HOURS`, padrão 24h)  
Retenção: 7 dias (configurável via `BACKUP_RETENTION_DAYS`)  
Armazenamento: MinIO, bucket `backups`

Bancos cobertos:
- PostgreSQL: iam_db, patient_db, clinical_db, reporting_db
- MongoDB: ai_db

Ver backups disponíveis (ADMIN):
```
GET /api/v1/admin/backups
```
Resposta: lista com `filename`, `size_mb`, `created_at`, `download_url` (pré-assinado 1h)

Logs do serviço de backup:
```bash
docker compose logs backup-service --tail=50
```

Restaurar PostgreSQL (exemplo):
```bash
gunzip -c backup_clinical_db_2026-06-01.sql.gz | docker compose exec -T db-clinical psql -U clinical -d clinical_db
```

Restaurar MongoDB (exemplo):
```bash
mongorestore --host localhost:27017 --username ai --password ai_pass --authenticationDatabase admin --gzip --archive=backup_ai_db_2026-06-01.gz
```
