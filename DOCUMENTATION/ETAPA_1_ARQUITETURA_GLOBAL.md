# ETAPA 1 — ARQUITETURA GLOBAL

# 1. DOMAIN ANALYSIS & BOUNDED CONTEXTS

O monólito original possui múltiplos domínios fortemente acoplados dentro do mesmo runtime.

A nova arquitetura distribui responsabilidades utilizando:

* Domain-Driven Design (DDD)
* Event-Driven Architecture (EDA)
* Clean Architecture
* Database-per-service
* API Gateway Pattern
* RabbitMQ
* CQRS-inspired reporting

---

# BOUNDED CONTEXT MAP

```mermaid
graph TD

IAM[Identity & Access Context]

PATIENT[Patient Management Context]

CLINICAL[Clinical Workflow Context]

AI[AI Assistance Context]

REPORTING[Reporting & Analytics Context]

IAM --> PATIENT
IAM --> CLINICAL
IAM --> REPORTING

PATIENT --> CLINICAL

CLINICAL --> AI

CLINICAL --> REPORTING

AI --> REPORTING
```

---

# 2. BOUNDED CONTEXTS

## 2.1 Identity & Access Context

### Responsabilidades

* Usuários
* Autenticação
* JWT
* RBAC
* Sessões
* Políticas de segurança

### Serviço

* IAM Service

---

## 2.2 Patient Context

### Responsabilidades

* Cadastro de pacientes
* Dados demográficos
* Metadados
* Informações de contato

### Serviço

* Patient Service

---

## 2.3 Clinical Context

### Responsabilidades

* Prontuários
* Prescrições
* Exames
* Uploads
* PDFs
* Histórico clínico
* Timeline médica

### Serviço

* Clinical Service

---

## 2.4 AI Assistance Context

### Responsabilidades

* NLP
* Resumos clínicos
* Sugestões médicas
* Orquestração de IA

### Serviço

* AI Service

---

## 2.5 Reporting Context

### Responsabilidades

* Dashboards
* KPIs
* Analytics
* Read models
* Relatórios

### Serviço

* Reporting Service

---

# 3. ESTRUTURA GLOBAL DO PROJETO

```text
backend/
├── api-gateway/
├── iam-service/
├── patient-service/
├── clinical-service/
├── ai-service/
├── reporting-service/
└── shared/

frontend/
└── src/
    ├── components/
    ├── pages/
    ├── services/
    ├── hooks/
    ├── contexts/
    ├── layouts/
    ├── routes/
    ├── utils/
    └── types/
```
---

# 4. C4 — CONTAINER DIAGRAM

```mermaid
C4Container
title Distributed Medical SaaS - Container Diagram

Person(user, "Users")

Container(frontend, "Frontend SPA", "React + TS + Tailwind")

Container(gateway, "API Gateway", "FastAPI")

Container(iam, "IAM Service", "FastAPI")
Container(patient, "Patient Service", "FastAPI")
Container(clinical, "Clinical Service", "FastAPI")
Container(ai, "AI Service", "FastAPI")
Container(reporting, "Reporting Service", "FastAPI")

ContainerDb(iamdb, "IAM DB", "PostgreSQL")
ContainerDb(patientdb, "Patient DB", "PostgreSQL")
ContainerDb(clinicaldb, "Clinical DB", "PostgreSQL")
ContainerDb(reportdb, "Reporting DB", "PostgreSQL")

ContainerQueue(rabbit, "RabbitMQ", "AMQP")

Container(storage, "Object Storage", "MinIO/S3")

Rel(user, frontend, "HTTPS")

Rel(frontend, gateway, "REST/JSON")

Rel(gateway, iam, "Auth APIs")
Rel(gateway, patient, "Patient APIs")
Rel(gateway, clinical, "Clinical APIs")
Rel(gateway, ai, "AI APIs")
Rel(gateway, reporting, "Reporting APIs")

Rel(iam, iamdb, "Owns")
Rel(patient, patientdb, "Owns")
Rel(clinical, clinicaldb, "Owns")
Rel(reporting, reportdb, "Owns")

Rel(clinical, storage, "Stores attachments")

Rel(patient, rabbit, "Publishes events")
Rel(clinical, rabbit, "Publishes events")
Rel(ai, rabbit, "Consumes/Publishes")
Rel(reporting, rabbit, "Consumes events")
```

---

# 5. API GATEWAY ARCHITECTURE

## Responsabilidades

* Roteamento centralizado
* JWT validation
* RBAC
* Aggregation layer
* Rate limiting
* Observabilidade
* Segurança

---

## Component Diagram

```mermaid
graph TD

ENTRY[Request Entry]

AUTH[JWT Middleware]

RBAC[RBAC Middleware]

ROUTER[Dynamic Router]

AGG[Aggregation Layer]

RATE[Rate Limiter]

CACHE[Gateway Cache]

OBS[Observability]

ENTRY --> AUTH
AUTH --> RBAC
RBAC --> ROUTER
ROUTER --> AGG
AGG --> RATE
RATE --> CACHE
CACHE --> OBS
```

---

## Estratégia de Roteamento

```text
/api/v1/auth/*        -> IAM Service
/api/v1/patients/*    -> Patient Service
/api/v1/clinical/*    -> Clinical Service
/api/v1/ai/*          -> AI Service
/api/v1/reports/*     -> Reporting Service
```

---

# 6. IAM SERVICE

## Responsabilidades

* Login
* JWT
* RBAC
* Usuários
* Roles
* Sessões

---

## Component Diagram

```mermaid
graph TD

API[REST API]

CTRL[Auth Controllers]

AUTHSVC[Authentication Service]

TOKENSVC[JWT Service]

RBACSVC[RBAC Service]

USERSVC[User Service]

REPO[Repositories]

DB[(IAM PostgreSQL)]

EVENTP[Event Producer]

API --> CTRL

CTRL --> AUTHSVC
CTRL --> USERSVC

AUTHSVC --> TOKENSVC
AUTHSVC --> RBACSVC

USERSVC --> REPO

REPO --> DB

USERSVC --> EVENTP
```

---

## Estrutura Interna

```text
iam-service/
├── app/
│   ├── api/
│   ├── auth/
│   ├── users/
│   ├── roles/
│   ├── jwt/
│   ├── repositories/
│   └── messaging/
```

---

## Database Ownership

Tabelas:

* users
* roles
* permissions
* refresh_tokens

---

## RabbitMQ

### Publica

* UserCreated
* UserRoleUpdated

### Consome

* Nenhum inicialmente

---

# 7. PATIENT SERVICE

## Responsabilidades

* Cadastro de pacientes
* Demografia
* Contatos
* Metadados
