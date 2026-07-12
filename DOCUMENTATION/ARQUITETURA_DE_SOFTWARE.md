# Representação da Arquitetura de Software

Este documento consolida a arquitetura utilizada no PROMPTUARIO Backend com base na implementação real do workspace.

---

## 1. Visão Geral

A solução adota uma arquitetura distribuída orientada a serviços, com separação por contexto de negócio e comunicação síncrona e assíncrona entre componentes.

### Características principais

- Microservices com responsabilidade delimitada por domínio
- API Gateway como ponto único de entrada
- JWT para autenticação e autorização
- Database per service
- Comunicação orientada a eventos com RabbitMQ
- Processamento assíncrono para análises e relatórios
- Observabilidade distribuída com métricas, logs e tracing
- Infraestrutura containerizada com Docker Compose

---

## 2. Estilo Arquitetural

| Camada | Papel |
|--------|------|
| Apresentação | Frontend React consumindo o Gateway |
| Borda | API Gateway com autenticação, rate limiting e roteamento |
| Domínio | Microserviços por contexto funcional |
| Persistência | Banco dedicado por serviço |
| Mensageria | RabbitMQ para eventos assíncronos |
| Processamento | Celery e workers para tarefas demoradas |
| Observabilidade | Prometheus, Grafana, Loki, Jaeger e Alertmanager |

---

## 3. Mapa de Serviços

| Serviço | Porta Host | Porta Container | Responsabilidade | Banco |
|---------|-----------|----------------|------------------|-------|
| Gateway | 8000 | 8000 | Entrada única, auth, proxy, health | Stateless |
| IAM | 8001 | 8000 | Autenticação, usuários, roles, OAuth2 | PostgreSQL |
| Patient | 8002 | 8000 | Pacientes, dados demográficos, histórico | PostgreSQL |
| Clinical | 8003 | 8000 | Agendamentos, prontuários, prescrições | PostgreSQL |
| AI | 8004 | 8000 | Análises clínicas assíncronas (IA) | MongoDB |
| Reporting | 8005 | 8000 | Relatórios, projeções, exportações | PostgreSQL |

---

## 4. Fluxo de Comunicação

```mermaid
flowchart LR
    CLIENT[Frontend] --> GATEWAY[Gateway]
    GATEWAY --> IAM[IAM]
    GATEWAY --> PATIENT[Patient]
    GATEWAY --> CLINICAL[Clinical]
    GATEWAY --> AI[AI]
    GATEWAY --> REPORTING[Reporting]

    IAM -->|JWT + blacklist| REDIS[(Redis)]
    CLINICAL -->|events| RABBIT[(RabbitMQ)]
    PATIENT -->|events| RABBIT
    AI -->|jobs| RABBIT
    REPORTING -->|consume projections| RABBIT
    REPORTING -->|store exports| MINIO[(MinIO)]
    CLINICAL -->|store documents| MINIO

    AI --> AIDB[(MongoDB)]
    IAM --> IAMDB[(PostgreSQL)]
    PATIENT --> PATIENTDB[(PostgreSQL)]
    CLINICAL --> CLINICALDB[(PostgreSQL)]
    REPORTING --> REPORTINGDB[(PostgreSQL)]
```

### Leitura do fluxo

- O frontend nunca acessa os serviços internos diretamente; tudo passa pelo Gateway.
- O Gateway valida o JWT e encaminha a requisição para o serviço correto.
- Serviços de domínio persistem dados em bancos próprios.
- Eventos de negócio seguem para o RabbitMQ para reduzir acoplamento.
- AI e Reporting executam tarefas assíncronas quando a operação não deve bloquear a requisição principal.

---

## 5. Padrões de Projeto Aplicados

- API Gateway Pattern
- Database per Service
- Event-Driven Architecture
- CQRS-inspired projections para relatórios
- Clean Architecture nos serviços de domínio
- Repository Pattern para persistência
- Async task processing para AI e Reporting
- Health checks por serviço e agregação no Gateway

---

## 6. Dependências Entre Serviços

| Origem | Destino | Motivo |
|--------|---------|--------|
| IAM | Gateway | Validação de tokens e controle de acesso |
| Patient | Clinical | Dados do paciente usados em atendimento |
| Clinical | AI | Solicitação de análise clínica |
| Clinical | Reporting | Geração de projeções e relatórios |
| AI | Reporting | Resultados analíticos reaproveitados em relatórios |
| Todos os serviços | Observabilidade | Métricas, logs e tracing |

---

## 7. Infraestrutura de Suporte

| Componente | Função |
|------------|--------|
| PostgreSQL 15 | Persistência relacional por serviço (4 bancos) |
| MongoDB 7 | Persistência documental do AI Service |
| Redis 7 | Cache, blacklist JWT, rate limiting, Celery broker |
| RabbitMQ 3.13 | Mensageria assíncrona entre serviços |
| MinIO | Armazenamento compatível com S3 (prescrições, relatórios, backups) |
| Prometheus | Coleta de métricas |
| Grafana | Dashboards e visualização |
| Loki | Centralização de logs |
| Jaeger + OpenTelemetry | Tracing distribuído |
| Alertmanager | Alertas operacionais |

---

## 8. Conclusão

A arquitetura combina serviços independentes, orquestração por container, comunicação assíncrona e observabilidade distribuída. O resultado é um desenho escalável, com menor acoplamento entre domínios e melhor capacidade de evolução por serviço.