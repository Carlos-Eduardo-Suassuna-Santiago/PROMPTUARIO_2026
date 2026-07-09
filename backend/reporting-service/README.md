# PROMPTUARIO — Reporting Service

O Reporting Service é o módulo responsável por gerar relatórios e exportações de dados do sistema. Ele processa solicitações de forma assíncrona, utilizando workers Celery para gerar arquivos CSV, JSON ou PDF e armazená-los no MinIO (S3).

## Contexto no ecossistema Promptuário

```
Gateway (:8000) → Reporting Service (:8005) → PostgreSQL / RabbitMQ / MinIO (S3)
                    │
                    └── Workers Celery: geração assíncrona de relatórios
```

O Reporting Service está posicionado atrás do **API Gateway** e se comunica com:
- **PostgreSQL** — persistência de jobs de relatório e estatísticas diárias (`DailyStats`)
- **RabbitMQ** — consumo de eventos de domínio para atualizar estatísticas em tempo real
- **MinIO (S3)** — armazenamento de relatórios exportados (CSV, PDF)

Porta padrão do serviço: `8005`

## Para que serve

Este microsserviço existe para transformar dados operacionais do sistema em relatórios úteis para administradores e médicos. Ele processa exportações de forma assíncrona, evitando que operações pesadas bloqueiem a API.

## Como funciona, passo a passo

1. Um usuário solicita um relatório via **Gateway**.
2. O serviço cria um **job** no banco de dados com status `PENDING`.
3. A tarefa é enviada para o **Celery worker**, que processa em segundo plano.
4. O worker gera o relatório (consulta dados, formata saída) e salva no **MinIO (S3)**.
5. O usuário pode consultar o status do job e, quando concluído, fazer o download via URL pré-assinada.
6. Paralelamente, o serviço consome eventos do RabbitMQ para manter estatísticas diárias atualizadas (`DailyStats`).

## O que ele faz na prática

- gera relatórios de consultas (CSV, JSON, PDF);
- gera relatórios de pacientes cadastrados;
- gera relatórios de produtividade por médico;
- exporta prescrições;
- mantém dashboard com estatísticas diárias (consultas hoje, novos pacientes do mês, cancelamentos);
- disponibiliza download via URL temporária (pre-signed URL do S3).

## Stack técnica

| Camada        | Tecnologia                        |
|---------------|-----------------------------------|
| API           | FastAPI 0.115+ (Python assíncrono)|
| BD Relacional | PostgreSQL 15 (SQLAlchemy 2 async)|
| Mensageria    | RabbitMQ 3.13 (aio-pika)          |
| Storage       | MinIO (S3-compatible)             |
| Workers       | Celery 5 + Redis broker           |
| Validação     | Pydantic v2                       |

## Pré-requisitos

- PostgreSQL disponível
- RabbitMQ disponível
- Redis disponível (broker do Celery)
- MinIO disponível (armazenamento de relatórios)
- Python 3.11+

## Início rápido

### Desenvolvimento local (sem Docker)

```bash
# Terminal 1: API
cd backend/reporting-service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8005

# Terminal 2: Worker Celery
celery -A app.workers.celery_tasks worker --loglevel=info
```

### Com Docker Compose (infraestrutura completa)

```bash
cd backend
docker-compose up --build reporting-service
```

## Endpoints principais

| Método | Endpoint                              | Descrição                                    |
|--------|---------------------------------------|----------------------------------------------|
| POST   | `/api/v1/reports/export`              | Solicita um relatório assíncrono             |
| GET    | `/api/v1/reports/export/{job_id}`     | Consulta o status do job                     |
| GET    | `/api/v1/reports/export/{job_id}/download` | Download do relatório (via S3 pre-signed URL) |
| GET    | `/api/v1/reports/consultations`       | Estatísticas diárias de consultas            |
| GET    | `/api/v1/reports/patients`            | Estatísticas diárias de novos pacientes      |
| GET    | `/api/v1/reports/doctors`             | Estatísticas de consultas por médico         |
| GET    | `/api/v1/reports/summary`             | Resumo rápido para dashboard (admin)         |
| GET    | `/healthz`                            | Health check do serviço                      |

### Tipos de relatório suportados

| Tipo            | Descrição                     | Formatos          |
|-----------------|-------------------------------|-------------------|
| `CONSULTATIONS` | Relatório de consultas        | JSON, CSV, PDF    |
| `PATIENTS`      | Relatório de pacientes        | JSON, CSV, PDF    |
| `DOCTORS`       | Relatório de médicos          | JSON, CSV, PDF    |
| `PRESCRIPTIONS` | Relatório de prescrições      | JSON, CSV, PDF    |

## Eventos de domínio

| Evento                   | Publica/Consome | Exchange               | Descrição                          |
|--------------------------|----------------|------------------------|------------------------------------|
| `AppointmentCreated`     | Consome        | `promptuario.clinical` | Incrementa consultas do dia        |
| `AppointmentCancelled`   | Consome        | `promptuario.clinical` | Incrementa cancelamentos do dia    |
| `PatientCreated`         | Consome        | `promptuario.patient`  | Incrementa novos pacientes do dia  |
| `MedicalRecordCreated`   | Consome        | `promptuario.clinical` | Incrementa consultas por médico    |

## Exemplo de uso

```bash
# 1. Solicitar relatório
JOB=$(curl -s -X POST http://localhost:8000/api/v1/reports/export \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"report_type": "CONSULTATIONS", "output_format": "CSV", "parameters": {"from_date": "2026-01-01"}}')

JOB_ID=$(echo $JOB | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")

# 2. Aguardar conclusão e baixar
curl -H "Authorization: Bearer <TOKEN>" \
  http://localhost:8000/api/v1/reports/export/$JOB_ID/download
```

> **Nota:** Os endpoints são acessados via **Gateway** (`:8000`), que faz o roteamento para o Reporting Service (`:8005`).

## Variáveis de ambiente importantes

| Variável              | Descrição                              | Default       |
|-----------------------|----------------------------------------|---------------|
| `DATABASE_URL`        | URL de conexão com PostgreSQL          | —             |
| `RABBITMQ_URL`        | URL de conexão com RabbitMQ            | —             |
| `REDIS_URL`           | URL de conexão com Redis (Celery)      | —             |
| `JWT_SECRET_KEY`      | Chave secreta JWT (≥32 caracteres)     | *obrigatório* |
| `JWT_ALGORITHM`       | Algoritmo JWT                          | `HS256`       |
| `S3_ENDPOINT`         | Endpoint MinIO/S3                      | —             |
| `S3_ACCESS_KEY`       | Access key do MinIO                    | —             |
| `S3_SECRET_KEY`       | Secret key do MinIO                    | —             |
| `S3_BUCKET_REPORTS`   | Bucket para relatórios                 | —             |
| `LOG_LEVEL`           | Nível de log                           | `INFO`        |
| `SERVICE_NAME`        | Nome do serviço (para RabbitMQ)        | `reporting`   |

## Como validar o funcionamento

- acesse `http://localhost:8005/healthz`;
- solicite um relatório via `POST /api/v1/reports/export`;
- consulte o status do job com o `job_id` retornado;
- faça o download quando o status for `COMPLETED`;
- verifique o dashboard em `GET /api/v1/reports/summary`.

## Testes

```bash
cd backend/reporting-service
pytest -q
```

## Documentação relacionada

- [Documentação técnica da etapa 7 (Reporting Service)](../../DOCUMENTATION/ETAPA_7_Reporting_Service_Fastapi_Production.md)
- [Modelo lógico do banco de dados](../../DOCUMENTATION/ETAPA_14_Modelo_Logico_Reporting_Service.md)
- [Arquitetura global do sistema](../../DOCUMENTATION/ETAPA_1_ARQUITETURA_GLOBAL.md)

## Observação final

Esse serviço transforma dados operacionais em informação estratégica. Com processamento assíncrono via Celery e armazenamento no S3, ele garante que relatórios complexos não impactem a performance da API principal.