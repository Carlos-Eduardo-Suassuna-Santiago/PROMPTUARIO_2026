# ETAPA 10 — INFRAESTRUTURA DISTRIBUÍDA

# 1. OBJETIVO

A infraestrutura será responsável por:

* Orquestração distribuída
* Comunicação entre microservices
* Persistência desacoplada
* Event-driven messaging
* Reverse proxy
* Service discovery
* Escalabilidade horizontal
* Isolamento de contexto
* Deploy consistente

---

# 2. VISÃO GERAL DA INFRAESTRUTURA

```mermaid
graph TD

CLIENT[Frontend React]

GATEWAY[API Gateway]

IAM[IAM Service]
PATIENT[Patient Service]
CLINICAL[Clinical Service]
AI[AI Service]
REPORTING[Reporting Service]

RABBIT[RabbitMQ]

IAMDB[(IAM DB - PostgreSQL)]
PATIENTDB[(Patient DB - PostgreSQL)]
CLINICALDB[(Clinical DB - PostgreSQL)]
REPORTINGDB[(Reporting DB - PostgreSQL)]
AIDB[(AI DB - MongoDB)]

CLIENT --> GATEWAY

GATEWAY --> IAM
GATEWAY --> PATIENT
GATEWAY --> CLINICAL
GATEWAY --> AI
GATEWAY --> REPORTING

IAM --> IAMDB
PATIENT --> PATIENTDB
CLINICAL --> CLINICALDB
REPORTING --> REPORTINGDB
AI --> AIDB

IAM --> RABBIT
PATIENT --> RABBIT
CLINICAL --> RABBIT
AI --> RABBIT
REPORTING --> RABBIT
```

---

# 3. MAPEAMENTO DE PORTAS (host:container)

| Serviço | Porta Host | Porta Container | Health Check |
|---------|-----------|----------------|--------------|
| gateway | 8000 | 8000 | /healthz |
| iam-service | 8001 | 8000 | /healthz |
| patient-service | 8002 | 8000 | /healthz |
| clinical-service | 8003 | 8000 | /healthz |
| ai-service | 8004 | 8000 | /healthz |
| reporting-service | 8005 | 8000 | /healthz |
| redis | 6379 | 6379 | redis-cli ping |
| rabbitmq | 5672/15672 | 5672/15672 | rabbitmq-diagnostics ping |
| minio | 9000/9001 | 9000/9001 | curl /minio/health/live |
| prometheus | 9090 | 9090 | - |
| grafana | 3001 | 3000 | - |
| jaeger | 16686 | 16686 | - |

---

# 4. DOCKER COMPOSE REAL

O `docker-compose.yml` real do projeto está em `backend/docker-compose.yml` e utiliza os seguintes padrões:

## Credenciais

| Componente | Usuário | Senha |
|-----------|---------|-------|
| RabbitMQ | promptuario | promptuario_pass |
| MinIO | promptuario | promptuario_pass |
| db-iam | iam | iam_pass |
| db-patient | patient | patient_pass |
| db-clinical | clinical | clinical_pass |
| db-reporting | reporting | reporting_pass |
| db-ai (MongoDB) | ai | ai_pass |

## URLs de Conexão (padrão)

```text
IAM:      postgresql+asyncpg://iam:iam_pass@db-iam:5432/iam_db
Patient:  postgresql+asyncpg://patient:patient_pass@db-patient:5432/patient_db
Clinical: postgresql+asyncpg://clinical:clinical_pass@db-clinical:5432/clinical_db
Reporting:postgresql+asyncpg://reporting:reporting_pass@db-reporting:5432/reporting_db
AI:       mongodb://ai:ai_pass@db-ai:27017/ai_db?authSource=admin
Redis:    redis://redis:6379/0
RabbitMQ: amqp://promptuario:promptuario_pass@rabbitmq:5672/
```

## Serviços do docker-compose.yml real

```yaml
services:
  # ─── DATABASES ────────────────────────────────────────────────
  db-iam:       # postgres:15-alpine, user: iam, db: iam_db
  db-patient:   # postgres:15-alpine, user: patient, db: patient_db
  db-clinical:  # postgres:15-alpine, user: clinical, db: clinical_db
  db-reporting: # postgres:15-alpine, user: reporting, db: reporting_db
  db-ai:        # mongo:7, user: ai, db: ai_db

  # ─── INFRASTRUCTURE ───────────────────────────────────────────
  redis:        # redis:7-alpine, port 6379
  rabbitmq:     # rabbitmq:3.13-management-alpine, ports 5672+15672
  minio:        # minio/minio:latest, ports 9000+9001

  # ─── MICROSERVICES ────────────────────────────────────────────
  iam-service:       # porta 8001:8000
  patient-service:   # porta 8002:8000
  clinical-service:  # porta 8003:8000
  clinical-worker:   # worker Celery para tarefas assíncronas
  ai-service:        # porta 8004:8000
  reporting-service: # porta 8005:8000
  reporting-worker:  # worker Celery para relatórios
  reporting-beat:    # scheduler Celery Beat

  # ─── API GATEWAY ──────────────────────────────────────────────
  gateway:       # porta 8000:8000

  # ─── OBSERVABILITY ────────────────────────────────────────────
  prometheus:    # prom/prometheus:v2.54.1, porta 9090
  grafana:       # grafana/grafana:11.2.2, porta 3001:3000
  jaeger:        # jaegertracing/all-in-one:1.58, porta 16686
  otel-collector:# otel/opentelemetry-collector-contrib:0.105.0, porta 4317

  # ─── BACKUP ───────────────────────────────────────────────────
  backup-service: # backup automatizado para MinIO
```

---

# 5. DOCKERFILES

## backend/*/Dockerfile (padrão)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Frontend Dockerfile

```dockerfile
FROM node:20 AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:stable-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

---

# 6. RABBITMQ SETUP

## Exchanges

| Exchange | Tipo |
| -------- | ---- |
| promptuario.iam | topic |
| promptuario.patient | topic |
| promptuario.clinical | topic |
| promptuario.ai | topic |
| promptuario.reporting | topic |
| promptuario.dlx | Dead Letter Exchange |

## Filas por Serviço

| Queue | Consumer |
| ----- | -------- |
| patient.iam.* | Patient Service |
| clinical.patient.* | Clinical Service |
| ai.clinical.* | AI Service |
| reporting.clinical.* | Reporting Service |

---

# 7. REDIS USAGE

| Finalidade | Chave | TTL |
|-----------|-------|-----|
| Blacklist JWT | blacklist:{token} | Variável |
| Rate Limiting | rate_limit:{user_id}:{ip} | 60s |
| Celery Broker | (default) | - |
| Cache de Jobs | (variável) | Variável |

---

# 8. MINIO BUCKETS

| Bucket | Finalidade |
|--------|-----------|
| prescriptions | PDFs de prescrições |
| reports | Relatórios exportados (CSV/PDF) |
| backups | Backups automáticos |

---

# Quickstart padronizado

```bash
cd backend
docker compose up -d

# Verificar health checks
curl http://localhost:8000/healthz
curl http://localhost:8001/healthz
curl http://localhost:8002/healthz
curl http://localhost:8003/healthz
curl http://localhost:8004/healthz
curl http://localhost:8005/healthz
```

O conjunto acima valida a infraestrutura principal no mesmo layout usado pelo `docker-compose.yml` do backend.