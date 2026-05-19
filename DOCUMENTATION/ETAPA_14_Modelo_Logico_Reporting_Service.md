# ETAPA 14.4 — REPORTING SERVICE

Este documento descreve o modelo lógico do Reporting Service, responsável por jobs assíncronos de exportação e agregações de leitura.

## Tabelas

### report_jobs

| Campo | Tipo | Nulo | Chave | Descrição |
|------|------|------|------|-----------|
| id | UUID/String(36) | Não | PK | Identificador do job |
| report_type | enum | Não | - | CONSULTATIONS, PATIENTS, DOCTORS, PRESCRIPTIONS |
| requested_by | UUID/String(36) | Não | - | Solicitante |
| parameters | JSON | Não | - | Filtros e parâmetros |
| status | enum | Não | - | PENDING, RUNNING, COMPLETED, FAILED |
| output_format | enum | Não | - | JSON, CSV, PDF |
| result_data | JSON | Sim | - | Resultado em memória |
| s3_key | varchar(500) | Sim | - | Arquivo exportado |
| error_message | text | Sim | - | Erro de processamento |
| row_count | integer | Não | - | Quantidade de linhas |
| created_at | datetime tz | Não | - | Criação |
| completed_at | datetime tz | Sim | - | Finalização |

### daily_stats

| Campo | Tipo | Nulo | Chave | Descrição |
|------|------|------|------|-----------|
| id | UUID/String(36) | Não | PK | Identificador do agregado |
| stat_date | varchar(10) | Não | Índice | Data no formato YYYY-MM-DD |
| stat_type | varchar(50) | Não | - | Tipo da métrica |
| entity_id | UUID/String(36) | Sim | - | Entidade relacionada |
| value | integer | Não | - | Valor agregado |

## Relacionamentos

- `report_jobs` representa tarefas assíncronas de exportação.
- `daily_stats` é uma tabela de projeção/aggregate, alimentada por consumidores de eventos.