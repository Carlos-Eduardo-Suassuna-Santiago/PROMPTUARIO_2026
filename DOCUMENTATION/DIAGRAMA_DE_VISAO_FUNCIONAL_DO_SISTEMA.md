# Visão Funcional do Sistema

**Data:** 15 de julho de 2026  
**Versão:** 1.1.0

Este diagrama consolida a visão funcional do **PROMPTUARIO** a partir dos atores de negócio, dos módulos de domínio e dos fluxos principais de uso, incluindo circuit breaker, cache, eventos assíncronos e observabilidade.

```mermaid
flowchart TB
    subgraph ATORES["🎭 Atores do Sistema"]
        PACIENTE["🧑 Paciente"]
        MEDICO["👨‍⚕️ Médico"]
        ATENDENTE["👩 Atendente"]
        ADMIN["🔐 Administrador"]
        OPERADOR["📊 Operador"]
    end

    subgraph APRESENTACAO["🖥️ Camada de Apresentação"]
        PORTAL_WEB["Portal Web\nReact + TypeScript + Tailwind"]
    end

    subgraph GATEWAY["🔀 API Gateway (:8000)"]
        direction TB
        GW_AUTH["Middleware JWT\nBlacklist Redis"]
        GW_RATE["Rate Limiting\n30/min anônimo · 300/min autenticado"]
        GW_CB["Circuit Breaker\n3 falhas → open 30s"]
        GW_CACHE["Cache GET · TTL 60s · Gzip"]
        GW_ROUTE["Roteamento\n/auth → IAM · /patients → Patient\n/appointments → Clinical\n/ai → AI · /reports → Reporting"]
    end

    subgraph IDENTIDADE["🔐 IAM Service (:8001)"]
        direction TB
        IAM_AUTH["Login · Refresh · Logout · 2FA · OAuth2"]
        IAM_USERS["CRUD Usuários\nRoles: ADMIN · DOCTOR · ATTENDANT · PATIENT"]
        IAM_EVENTS["Eventos\nUserCreated · UserDeactivated"]
    end

    subgraph PACIENTE_MODULO["👤 Patient Service (:8002)"]
        direction TB
        PAT_CAD["Cadastro · CPF · Contato"]
        PAT_CLIN["Alergias · Vacinas · Medicações"]
        PAT_LGPD["Anonimização LGPD"]
        PAT_EVENTS["Eventos\nPatientCreated · PatientUpdated · AllergyAdded"]
    end

    subgraph CLINICO["🏥 Clinical Service (:8003)"]
        direction TB
        CLIN_AGENDA["Agenda Médica · Slots"]
        CLIN_CONSULTA["Consultas\nAgendamento · Cancelamento"]
        CLIN_PRONT["Prontuários\nRegistro imutável · Diagnósticos"]
        CLIN_PRESC["Prescrições\nMedicamentos · PDF em MinIO"]
        CLIN_EVENTS["Eventos\nAppointmentCreated · AppointmentCancelled\nMedicalRecordCreated · PrescriptionGenerated"]
    end

    subgraph IA["🤖 AI Service (:8004)"]
        direction TB
        IA_DRUG["Interação Medicamentosa"]
        IA_SYMPTOM["Análise de Sintomas"]
        IA_SUMMARY["Resumo Clínico"]
        IA_JOBS["Jobs Assíncronos\nPENDING → COMPLETED"]
    end

    subgraph REPORTING_MODULO["📊 Reporting Service (:8005)"]
        direction TB
        REP_EXPORT["Exportação\nCSV · JSON · PDF · Celery Workers"]
        REP_DASH["Dashboard\nConsultas/dia · Métricas operacionais"]
        REP_EVENTS["Consome Eventos\nAppointmentCreated · PatientCreated"]
    end

    subgraph OBSERVABILIDADE["📈 Observabilidade"]
        direction TB
        OBS_LOGS["Logs · Loki + Grafana"]
        OBS_METRICS["Métricas · Prometheus"]
        OBS_TRACING["Tracing · OpenTelemetry + Jaeger"]
        OBS_ALERT["Alertas · Alertmanager"]
    end

    subgraph INFRA_APOIO["🛠️ Infraestrutura"]
        direction TB
        RABBITMQ["🐰 RabbitMQ · Event Bus\nDLX · Dead Letter Queue"]
        REDIS["🔥 Redis\nCache · Blacklist · Rate Limit · Celery Broker"]
        MINIO["📦 MinIO (S3)\nPDFs · Relatórios · Backups"]
    end

    %% Conexões dos Atores
    PACIENTE --> PORTAL_WEB
    MEDICO --> PORTAL_WEB
    ATENDENTE --> PORTAL_WEB
    ADMIN --> PORTAL_WEB
    OPERADOR --> OBSERVABILIDADE

    %% Fluxo Principal Gateway
    PORTAL_WEB --> GW_AUTH
    GW_AUTH --> GW_RATE
    GW_RATE --> GW_CB
    GW_CB --> GW_CACHE
    GW_CACHE --> GW_ROUTE

    %% Roteamento
    GW_ROUTE -->|/auth| IAM_AUTH
    GW_ROUTE -->|/users| IAM_USERS
    GW_ROUTE -->|/patients| PAT_CAD
    GW_ROUTE -->|/appointments| CLIN_CONSULTA
    GW_ROUTE -->|/records| CLIN_PRONT
    GW_ROUTE -->|/schedules| CLIN_AGENDA
    GW_ROUTE -->|/ai| IA_JOBS
    GW_ROUTE -->|/reports| REP_EXPORT

    %% Fluxos de Negócio
    PAT_CAD --> CLIN_CONSULTA
    CLIN_PRONT --> IA_JOBS
    CLIN_PRESC --> IA_DRUG
    CLIN_EVENTS --> RABBITMQ
    PAT_EVENTS --> RABBITMQ
    IA_JOBS --> RABBITMQ
    RABBITMQ --> REP_EVENTS

    %% Infraestrutura
    IAM_AUTH --> REDIS
    GW_RATE --> REDIS
    CLIN_PRESC --> MINIO
    REP_EXPORT --> MINIO

    %% Observabilidade
    GW_ROUTE -.-> OBS_METRICS
    IAM_AUTH -.-> OBS_METRICS
    PAT_CAD -.-> OBS_METRICS
    CLIN_CONSULTA -.-> OBS_METRICS
    IA_JOBS -.-> OBS_METRICS
    REP_EXPORT -.-> OBS_METRICS
```

## Leitura da Visão

- Os **atores** acessam o sistema pelo portal web (React + TypeScript), que centraliza as interações com o Gateway.
- O **API Gateway** distribui as requisições para os serviços adequados, aplicando JWT validation, rate limiting (Redis), circuit breaker (3 falhas → open 30s) e cache GET (TTL 60s).
- O **IAM Service** controla identidade, autenticação (incluindo OAuth2 Google e 2FA), autorização RBAC e gerenciamento de usuários.
- O **Patient Service** organiza o cadastro, dados demográficos, alergias, vacinas, medicações contínuas e anonimização LGPD.
- O **Clinical Service** concentra o fluxo assistencial principal: agenda médica, consultas, prontuários (com histórico imutável), prescrições e solicitações de exame.
- O **AI Service** executa análises assíncronas (interação medicamentosa, análise de sintomas, resumo clínico) com integração LLM (OpenAI).
- O **Reporting Service** consolida informações para relatórios e exportações (CSV, JSON, PDF) com workers Celery e agendamento via Celery Beat.
- A **observabilidade** acompanha toda a operação via Prometheus + Grafana + Loki + Jaeger + Alertmanager.
- A **infraestrutura** utiliza RabbitMQ (event bus com DLX), Redis (cache, rate limit, blacklist, broker Celery) e MinIO (storage S3 para PDFs e relatórios).

## Fluxo de Eventos (RabbitMQ)

| Evento | Publicador | Consumidores |
|--------|-----------|--------------|
| UserCreatedEvent | IAM | Patient |
| UserDeactivatedEvent | IAM | Patient, Clinical |
| PatientCreatedEvent | Patient | Clinical, Reporting |
| PatientUpdatedEvent | Patient | Clinical |
| AllergyAddedEvent | Patient | - |
| AppointmentCreatedEvent | Clinical | Reporting, AI |
| AppointmentCancelledEvent | Clinical | Reporting |
| MedicalRecordCreatedEvent | Clinical | AI, Reporting |
| PrescriptionGeneratedEvent | Clinical | AI, Reporting |
| AnalysisCompletedEvent | AI | - |

## Relação com a Documentação Existente

Este diagrama complementa o documento de [casos de uso](DIAGRAMA_DE_CASOS_DE_USO.md) e a [arquitetura de software](ARQUITETURA_DE_SOFTWARE.md), mantendo a mesma divisão por domínios do sistema.

---

**Documento Gerado:** 15 de julho de 2026  
**Versão:** 1.1.0  
**Diagrama:** `DOCUMENTATION/DIAGRAMS/Visao_Funcional_Sistema.png`