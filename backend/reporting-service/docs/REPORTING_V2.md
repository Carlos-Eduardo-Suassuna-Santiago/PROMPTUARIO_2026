# Reporting Service v2 — Agendamento, Webhooks, XLSX e Relatórios Customizados

## Visão Geral

Esta versão estende o Reporting Service com quatro capacidades principais:

1. **Agendamento Recorrente** — relatórios executados automaticamente via cron expression, gerenciados por Celery Beat.
2. **Notificações por Webhook** — payload assinado com HMAC-SHA256 enviado para endpoints externos quando um job termina.
3. **Exportação XLSX Multi-Aba** — geração de arquivos Excel com múltiplas planilhas, cabeçalhos estilizados e largura auto-ajustada.
4. **Relatórios Customizados** — templates SQL pré-aprovados executados com parâmetros validados (sem risco de SQL injection).

## Arquitetura

```
┌─────────────┐     POST /api/v1/reports/export     ┌──────────────────┐
│   Cliente   │ ──────────────────────────────────►  │  FastAPI (main)  │
│  (Admin/    │                                      │                  │
│   Doctor)   │ ◄──────────────────────────────────  │  - Valida auth   │
└─────────────┘     GET /api/v1/reports/export/{id}  │  - Cria job      │
                                                     │  - Audit log     │
                                                     │  - Envia task    │
                                                     └────────┬─────────┘
                                                              │
                                              celery_app.send_task()
                                                              │
                                                     ┌────────▼─────────┐
                                                     │  Celery Worker   │
                                                     │  (celery_tasks)  │
                                                     │                  │
                                                     │  1. Gera dados   │
                                                     │  2. Sobe para S3 │
                                                     │  3. Audit log    │
                                                     │  4. Webhook      │
                                                     └──────────────────┘
```

## Novas Entidades (SQLAlchemy)

| Tabela | Descrição |
|--------|-----------|
| `report_schedules` | Configuração de agendamento recorrente (cron, tipo, formato) |
| `webhook_configs` | Endpoints webhook registrados (URL, secret, eventos, retry) |
| `webhook_delivery_logs` | Histórico de entregas de webhook (status, tentativa, erro) |
| `report_audit_logs` | Auditoria específica do reporting service |

## Endpoints

### Agendamento (`/api/v1/schedules`)

| Método | Path | Descrição |
|--------|------|-----------|
| POST | `/schedules` | Criar agendamento recorrente |
| GET | `/schedules` | Listar agendamentos (paginado) |
| GET | `/schedules/{id}` | Obter detalhes de um agendamento |
| PUT | `/schedules/{id}` | Atualizar agendamento |
| DELETE | `/schedules/{id}` | Remover agendamento |
| POST | `/schedules/{id}/trigger` | Executar manualmente agora |

**Payload de criação:**
```json
{
  "name": "Relatório Diário de Consultas",
  "report_type": "CONSULTATIONS",
  "output_format": "XLSX",
  "cron_expression": "0 6 * * *",
  "parameters": {},
  "recipients": ["admin@exemplo.com"],
  "active": true
}
```

### Webhooks (`/api/v1/webhooks`)

| Método | Path | Descrição |
|--------|------|-----------|
| POST | `/webhooks` | Registrar webhook |
| GET | `/webhooks` | Listar webhooks |
| GET | `/webhooks/{id}` | Obter detalhes |
| PUT | `/webhooks/{id}` | Atualizar webhook |
| DELETE | `/webhooks/{id}` | Remover webhook |
| GET | `/webhooks/{id}/deliveries` | Histórico de entregas |

**Payload de criação:**
```json
{
  "url": "https://meu-sistema.com/webhook/report",
  "secret": "minha-chave-secreta-16-caracteres",
  "description": "Webhook produção",
  "active": true,
  "max_retries": 3,
  "retry_interval_seconds": 60,
  "events": ["report.completed", "report.failed"]
}
```

### Exportação Avançada (`/api/v1/reports/export`)

| Método | Path | Descrição |
|--------|------|-----------|
| POST | `/reports/export` | Exportar relatório (agora aceita XLSX e CUSTOM) |
| POST | `/reports/export/custom` | Relatório customizado com template SQL |
| POST | `/reports/export/multi-sheet` | XLSX com múltiplas abas |
| GET | `/reports/export/{id}` | Status do job |
| GET | `/reports/export/{id}/download` | Download do arquivo |

**Multi-sheet request:**
```json
{
  "output_format": "XLSX",
  "filename": "relatorio_completo.xlsx",
  "sheets": [
    {
      "sheet_name": "Consultas",
      "report_type": "CONSULTATIONS",
      "parameters": {"from_date": "2025-01-01", "to_date": "2025-12-31"}
    },
    {
      "sheet_name": "Pacientes",
      "report_type": "PATIENTS",
      "parameters": {"from_date": "2025-01-01", "to_date": "2025-12-31"}
    }
  ]
}
```

### Auditoria (`/api/v1/audit`)

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/audit/logs` | Logs de auditoria do reporting (filtros: event_type, entity_type, data) |
| GET | `/audit/summary` | Resumo agregado por tipo de evento e usuário |

## Webhook — Payload e Assinatura

Quando um job é concluído, o worker envia um POST para cada webhook configurado:

**Headers:**
- `Content-Type: application/json`
- `X-Webhook-Signature: sha256=<HMAC-SHA256 do body>`
- `X-Webhook-Event: report.completed` (ou `report.failed`)
- `X-Webhook-Job-Id: <job_id>`

**Payload (completado):**
```json
{
  "event": "report.completed",
  "job_id": "abc-123",
  "report_type": "CONSULTATIONS",
  "output_format": "XLSX",
  "status": "COMPLETED",
  "row_count": 150,
  "s3_key": "reports/consultations/abc-123.xlsx",
  "completed_at": "2025-06-15T10:30:00Z"
}
```

**Payload (falha):**
```json
{
  "event": "report.failed",
  "job_id": "abc-123",
  "report_type": "CONSULTATIONS",
  "output_format": "XLSX",
  "status": "FAILED",
  "error": "Connection timeout",
  "failed_at": "2025-06-15T10:30:00Z"
}
```

## Templates SQL Customizados

Definidos em `config.py` → `CUSTOM_SQL_TEMPLATES`. Apenas templates pré-aprovados são executáveis. Parâmetros são validados (apenas str/int/float/bool, máx 500 chars).

Templates disponíveis:
- `consultations_by_doctor` — consultas agrupadas por médico
- `patient_growth` — novos pacientes por dia
- `cancellation_rate` — taxa de cancelamento diária

## Celery Beat — Sincronização Dinâmica

O worker escuta o sinal `beat_init` para carregar schedules ativos do banco. Sempre que um schedule é criado/alterado/excluído via API, uma task `reporting.refresh_beat_schedules` é disparada para re-sincronizar.

## Segurança

- **SQL Injection:** relatórios customizados usam apenas templates pré-aprovados com bind parameters.
- **Webhook:** payload assinado com HMAC-SHA256 usando secret compartilhado.
- **Auditoria:** toda operação (criação, execução, falha) é registrada em `report_audit_logs`.
- **Parâmetros:** validados por Pydantic (tipos permitidos, tamanho máximo).

## Testes

```bash
cd backend/reporting-service
pip install -r requirements.txt
pytest tests/ -v
```

Testes cobrem:
- Schemas (validação de schedules, webhooks, custom reports, multi-sheet)
- XLSX builder (single e multi-sheet, dados vazios)