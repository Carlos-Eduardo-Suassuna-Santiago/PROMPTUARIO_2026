# ETAPA 7 — REPORTING SERVICE (FASTAPI)

# 1. OBJETIVO

O `reporting-service` será responsável por:

* Read models otimizados
* Analytics clínicos
* Dashboards
* Métricas operacionais
* Projeções assíncronas
* Queries agregadas
* Sincronização eventual
* CQRS-inspired architecture

O serviço NÃO será responsável por operações transacionais.

Ele consumirá eventos de domínio para construir modelos materializados.

---

# 2. RESPONSABILIDADES

| Módulo               | Responsabilidade           |
| -------------------- | -------------------------- |
| Projection Engine    | Atualização de read models |
| Analytics Engine     | Métricas agregadas         |
| Reporting API        | Endpoints analíticos       |
| Event Consumers      | Consumo RabbitMQ           |
| Read Database        | Dados desnormalizados      |
| Projection Rebuilder | Reprocessamento            |

---

# 3. ARQUITETURA CQRS-INSPIRED

```mermaid
graph TD

WRITE[Write Services]

RABBIT[(RabbitMQ)]

PROJECTION[Projection Engine]

READDB[(Reporting DB)]

API[Reporting API]

CLIENT[Frontend Dashboard]

WRITE --> RABBIT

RABBIT --> PROJECTION

PROJECTION --> READDB

CLIENT --> API

API --> READDB
```

---

# 4. ESTRUTURA DO PROJETO

```text
reporting-service/
├── app/
│
│   ├── api/
│   │   ├── router.py
│   │   └── v1/
│   │       ├── analytics_routes.py
│   │       ├── patient_reports_routes.py
│   │       └── clinical_reports_routes.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── logging.py
│   │
│   ├── domain/
│   │   └── models/
│   │       ├── patient_projection.py
│   │       ├── medical_record_projection.py
│   │       ├── prescription_projection.py
│   │       └── analytics_snapshot.py
│   │
│   ├── schemas/
│   │   ├── analytics_schema.py
│   │   
│   └── main.py

---

# Detalhes de implementação (extraído do ambiente)

- **Base path:** /api/v1 (endpoints expostos em `/api/v1/reports` e `/api/v1/reports/export`)
- **Health endpoint:** /healthz
- **Host port mapping (host:container):** 8005:8000
- **Principais variáveis de ambiente:**
	- `DATABASE_URL` (ex: postgresql+asyncpg://reporting:reporting_pass@db-reporting:5432/reporting_db)
	- `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` (ex: redis://redis:6379/1)
	- `RABBITMQ_URL` (ex: amqp://promptuario:promptuario_pass@rabbitmq:5672/)
	- `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET_REPORTS`
	- `JWT_SECRET_KEY`, `JWT_ALGORITHM`

Esses valores são necessários para a geração de relatórios assíncronos e para o worker Celery.

---

# Quickstart padronizado

```bash
curl http://localhost:8005/healthz
curl http://localhost:8005/docs
```

Via gateway, os relatórios ficam em `http://localhost:8000/api/v1/reports/*`.
```