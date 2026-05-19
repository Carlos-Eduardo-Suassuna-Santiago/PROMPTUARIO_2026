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

IAMDB[(IAM DB)]
PATIENTDB[(Patient DB)]
CLINICALDB[(Clinical DB)]
REPORTINGDB[(Reporting DB)]

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

IAM --> RABBIT
PATIENT --> RABBIT
CLINICAL --> RABBIT
AI --> RABBIT
REPORTING --> RABBIT
```

---

# 3. ESTRUTURA DE INFRAESTRUTURA

```text
infrastructure/

├── docker-compose.yml
│
├── .env
│
├── gateway/
│   └── Dockerfile
│
├── iam-service/
│   └── Dockerfile
│
├── patient-service/
│   └── Dockerfile
│
├── clinical-service/
│   └── Dockerfile
│
├── ai-service/
│   └── Dockerfile
│
├── reporting-service/
│   └── Dockerfile
│
├── frontend/
│   └── Dockerfile
│
├── rabbitmq/
│   ├── definitions.json
│   └── rabbitmq.conf
│
└── nginx/
    └── nginx.conf
```

---

# 4. DOCKER NETWORKING

# Estratégia

A arquitetura utiliza:

* Rede bridge isolada
* DNS interno Docker
* Comunicação service-to-service
* Containers independentes
* Service name resolution

---

# Rede Principal

```yaml
networks:
  medical-network:
    driver: bridge
```

---

# 5. DOCKER COMPOSE

# docker-compose.yml

```yaml
version: "3.9"

services:

  frontend:
    build:
      context: ../frontend
    container_name: frontend
    ports:
      - "3000:80"
    environment:
      - VITE_API_URL=http://localhost:8000
    depends_on:
      - api-gateway
    networks:
      - medical-network

  api-gateway:
    build:
      context: ../backend/api-gateway
    container_name: api-gateway
    ports:
      - "8000:8000"
    environment:
      - IAM_SERVICE_URL=http://iam-service:8001
      - PATIENT_SERVICE_URL=http://patient-service:8002
      - CLINICAL_SERVICE_URL=http://clinical-service:8003
      - AI_SERVICE_URL=http://ai-service:8004
      - REPORTING_SERVICE_URL=http://reporting-service:8005
      - JWT_SECRET=supersecret
    depends_on:
      - iam-service
      - patient-service
      - clinical-service
      - ai-service
      - reporting-service
    networks:
      - medical-network

  iam-service:
    build:
      context: ../backend/iam-service
    container_name: iam-service
    ports:
      - "8001:8001"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@iam-db:5432/iam
      - JWT_SECRET=supersecret
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
    depends_on:
      - iam-db
      - rabbitmq
    networks:
      - medical-network

  patient-service:
    build:
      context: ../backend/patient-service
    container_name: patient-service
    ports:
      - "8002:8002"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@patient-db:5432/patient
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
    depends_on:
      - patient-db
      - rabbitmq
    networks:
      - medical-network

  clinical-service:
    build:
      context: ../backend/clinical-service
    container_name: clinical-service
    ports:
      - "8003:8003"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@clinical-db:5432/clinical
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
      - S3_ENDPOINT=http://minio:9000
      - S3_ACCESS_KEY=minio
      - S3_SECRET_KEY=minio123
    depends_on:
      - clinical-db
      - rabbitmq
    networks:
      - medical-network

  ai-service:
    build:
      context: ../backend/ai-service
    container_name: ai-service
    ports:
      - "8004:8004"
    environment:
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
    depends_on:
      - rabbitmq
    networks:
      - medical-network

  reporting-service:
    build:
      context: ../backend/reporting-service
    container_name: reporting-service
    ports:
      - "8005:8005"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@reporting-db:5432/reporting
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
    depends_on:
      - reporting-db
      - rabbitmq
    networks:
      - medical-network

  rabbitmq:
    image: rabbitmq:3-management
    container_name: rabbitmq
    ports:
      - "5672:5672"
      - "15672:15672"
    volumes:
      - rabbitmq-data:/var/lib/rabbitmq
    networks:
      - medical-network

  iam-db:
    image: postgres:16
    container_name: iam-db
    environment:
      POSTGRES_DB: iam
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - iam-db-data:/var/lib/postgresql/data
    networks:
      - medical-network

  patient-db:
    image: postgres:16
    container_name: patient-db
    environment:
      POSTGRES_DB: patient
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - patient-db-data:/var/lib/postgresql/data
    networks:
      - medical-network

  clinical-db:
    image: postgres:16
    container_name: clinical-db
    environment:
      POSTGRES_DB: clinical
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - clinical-db-data:/var/lib/postgresql/data
    networks:
      - medical-network

  reporting-db:
    image: postgres:16
    container_name: reporting-db
    environment:
      POSTGRES_DB: reporting
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - reporting-db-data:/var/lib/postgresql/data
    networks:
      - medical-network

volumes:
  rabbitmq-data:
  iam-db-data:
  patient-db-data:
  clinical-db-data:
  reporting-db-data:

networks:
  medical-network:
    driver: bridge
```

---

# 6. DOCKERFILES

# Base Pattern

## backend/*/Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD [
  "uvicorn",
  "app.main:app",
  "--host",
  "0.0.0.0",
  "--port",
  "8000"
]
```

---

# Frontend Dockerfile

## frontend/Dockerfile

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

# 7. RABBITMQ SETUP

# Arquitetura

RabbitMQ será:

* Event bus central
* Async communication layer
* Retry coordinator
* DLQ handler

---

# Exchanges

| Exchange         | Tipo  |
| ---------------- | ----- |
| medical.events   | topic |
| patient.events   | topic |
| reporting.events | topic |

---

# Mapeamento real extraído de `promptuario-backend/docker-compose.yml`

Os serviços no `docker-compose.yml` do projeto usam os seguintes mapeamentos de porta (host:container) e endpoints:

- `gateway` → 8000:8000 (porta pública do API Gateway)
- `iam-service` → 8001:8000
- `patient-service` → 8002:8000
- `clinical-service` → 8003:8000
- `ai-service` → 8004:8000
- `reporting-service` → 8005:8000

Cada serviço expõe um health-check em `/healthz` e serve a API sob o prefixo `/api/v1`.

Infra adicionais:

- `redis` → 6379:6379
- `rabbitmq` → 5672:5672 e 15672:15672 (console)
- `minio` → 9000:9000 e 9001:9001 (console)

Use estes valores para sincronizar os exemplos de deploy e os guias de Quickstart.

---

# Quickstart padronizado

```bash
docker compose up -d
curl http://localhost:8000/healthz
curl http://localhost:8001/healthz
curl http://localhost:8002/healthz
curl http://localhost:8003/healthz
curl http://localhost:8004/healthz
curl http://localhost:8005/healthz
```

O conjunto acima valida a infraestrutura principal no mesmo layout usado pelo `docker-compose.yml` do backend.
