# Arquitetura C4

## Nível 1 — Contexto
ASCII diagram:
```
[ADMIN]   [DOCTOR]   [ATTENDANT]   [PATIENT]
    \         |           |            /
             ↓ ↓ ↓ ↓ ↓ ↓
         [PROMPTUÁRIO EHR System]
               /     |      \
              ↓      ↓       ↓
        [OpenAI API] [MinIO Storage] [RabbitMQ]
```

## Nível 2 — Containers
| Container | Tecnologia | Porta | Responsabilidade |
|---|---:|---:|---|
| Frontend | React + TypeScript | :3000 | Interface web do usuário |
| API Gateway | FastAPI | :8000 | Proxy, JWT, rate limiting, roteamento |
| IAM Service | FastAPI + PostgreSQL | :8001 | Autenticação, usuários, OAuth |
| Patient Service | FastAPI + PostgreSQL | :8002 | Gestão de pacientes, histórico |
| Clinical Service | FastAPI + PostgreSQL | :8003 | Agendamentos, prontuários, prescrições |
| AI Service | FastAPI + MongoDB | :8004 | Análises clínicas com LLMs/IA |
| Reporting Service | FastAPI + PostgreSQL + Celery | :8005 | Geração de relatórios assíncronos |
| RabbitMQ | RabbitMQ 3.13 | :5672 / :15672 | Mensageria de eventos |
| Redis | Redis 7 | :6379 | Cache, sessões, backend Celery |
| MinIO | MinIO (S3) | :9000 / :9001 | Armazenamento de arquivos (PDF, backups) |
| Prometheus | Prometheus 2.54 | :9090 | Coleta de métricas |
| Grafana | Grafana 11 | :3001 | Dashboards |
| Jaeger | Jaeger 1.58 | :16686 | Distributed tracing |

## Nível 3 — Componentes (por serviço)
- IAM Service:
  - `api/routers.py` (endpoints)
  - `domain/services/auth_service.py` (login, jwt)
  - `domain/models/user.py` (Pydantic / domain model)
  - `infrastructure/repositories/user_repository.py` (DB access)
  - `domain/services/oauth_service.py` (OAuth flows)
- Patient Service:
  - estrutura similar: `api/routers.py`, `domain/services/patient_service.py`, `infrastructure/repositories/patient_repository.py`
- Clinical Service:
  - inclui `workers/` para geração de PDFs, `domain/services/appointment_service.py` e `domain/services/medical_record_service.py`
- AI Service:
  - `domain/services/ai_service.py` (orquestra análise)
  - `infrastructure/llm_client.py` (cliente LLM/OpenAI)
  - armazenamento de resultados em MongoDB
- Reporting Service:
  - `app/main.py`, `workers/celery_tasks.py`, job queue (Celery + Redis), geração e armazenamento de relatórios em MinIO

## Eventos de domínio (RabbitMQ)
Tabela: Evento | Exchange | Publisher | Consumers
| Evento | Exchange | Publisher | Consumers |
|---|---:|---:|---|
| UserCreated | promptuario.iam | iam-service | gateway, patient-service, reporting-service |
| UserDeactivated | promptuario.iam | iam-service | iam-service, reporting-service |
| UserUpdated | promptuario.iam | iam-service | patient-service, clinical-service |
| PatientCreated | promptuario.patient | patient-service | reporting-service, ai-service |
| PatientUpdated | promptuario.patient | patient-service | clinical-service, reporting-service |
| AllergyAdded | promptuario.patient | patient-service | clinical-service, reporting-service |
| AppointmentCreated | promptuario.clinical | clinical-service | ai-service, reporting-service, gateway |
| AppointmentCancelled | promptuario.clinical | clinical-service | reporting-service, patient-service |
| MedicalRecordCreated | promptuario.clinical | clinical-service | ai-service, reporting-service |
| PrescriptionGenerated | promptuario.clinical | clinical-service | patient-service, reporting-service |
| AnalysisCompleted | promptuario.ai | ai-service | clinical-service, reporting-service |

(Exchanges em `shared/events/__init__.py`: promptuario.iam, promptuario.patient, promptuario.clinical, promptuario.ai, promptuario.dlx)
