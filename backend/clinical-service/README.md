# PROMPTUARIO — Clinical Service

O Clinical Service é o módulo responsável por organizar o fluxo clínico do sistema. Ele registra consultas, prontuários, prescrições e outras informações vinculadas ao atendimento.

## Contexto no ecossistema Promptuário

```
Gateway (:8000) → Clinical Service (:8003) → PostgreSQL / RabbitMQ / MinIO
                    │
                    └── gera eventos para IA, relatórios e outros serviços
```

O Clinical Service está posicionado atrás do **API Gateway** e se comunica com:
- **PostgreSQL** — persistência de consultas, prontuários, prescrições e agendas
- **RabbitMQ** — publicação de eventos de domínio (`AppointmentCreated`, `MedicalRecordCreated`, `PrescriptionGenerated`, etc.)
- **MinIO (S3)** — armazenamento de prescrições em PDF

Porta padrão do serviço: `8003`

## Para que serve

Este microsserviço existe para transformar o processo clínico em dados estruturados e confiáveis. Ele é o local onde as ações de atendimento deixam de ser apenas conversas e passam a virar registros digitais.

## Como funciona, passo a passo

1. Um paciente é agendado para atendimento.
2. O sistema cria ou atualiza a consulta.
3. O profissional registra as informações do atendimento no prontuário.
4. A prescrição e demais informações relacionadas podem ser salvas.
5. Esses dados ficam disponíveis para consulta e também geram eventos para outros serviços (AI Service, Reporting Service).

## O que ele faz na prática

- agenda consultas;
- organiza agendas médicas;
- cria prontuários clínicos;
- registra prescrições;
- publica eventos para integração com outros microsserviços.

## Stack técnica

| Camada        | Tecnologia                        |
|---------------|-----------------------------------|
| API           | FastAPI 0.115+ (Python assíncrono)|
| BD Relacional | PostgreSQL 15 (SQLAlchemy 2 async)|
| Mensageria    | RabbitMQ 3.13 (aio-pika)          |
| Storage       | MinIO (S3-compatible)             |
| Validação     | Pydantic v2                       |

## Pré-requisitos

- PostgreSQL disponível
- RabbitMQ disponível
- MinIO disponível (para upload de prescrições)
- Python 3.11+

## Início rápido

### Desenvolvimento local (sem Docker)

```bash
cd backend/clinical-service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8003
```

### Com Docker Compose (infraestrutura completa)

```bash
cd backend
docker-compose up --build clinical-service
```

## Endpoints principais

| Método | Endpoint                      | Descrição                     |
|--------|-------------------------------|-------------------------------|
| POST   | `/api/v1/appointments`        | Cria uma consulta             |
| GET    | `/api/v1/appointments`        | Lista consultas               |
| POST   | `/api/v1/records`             | Cria um prontuário            |
| GET    | `/api/v1/records`             | Consulta prontuários          |
| POST   | `/api/v1/schedules`           | Cadastra a agenda do médico   |
| GET    | `/healthz`                    | Health check do serviço       |

## Eventos de domínio

| Evento                   | Publica/Consome | Exchange               | Descrição                     |
|--------------------------|----------------|------------------------|-------------------------------|
| `AppointmentCreated`     | Publica        | `promptuario.clinical` | Consulta agendada             |
| `AppointmentCancelled`   | Publica        | `promptuario.clinical` | Consulta cancelada            |
| `MedicalRecordCreated`   | Publica        | `promptuario.clinical` | Prontuário criado             |
| `PrescriptionGenerated`  | Publica        | `promptuario.clinical` | Prescrição gerada             |

## Exemplo de uso

```bash
curl -X POST http://localhost:8000/api/v1/appointments \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "pat_123",
    "doctor_id": "doc_456",
    "scheduled_at": "2026-07-10T14:00:00Z",
    "appointment_type": "CONSULTATION",
    "specialty": "Clínica Geral"
  }'
```

> **Nota:** O endpoint é acessado via **Gateway** (`:8000`), que faz o roteamento para o Clinical Service (`:8003`).

## Variáveis de ambiente importantes

| Variável                      | Descrição                              | Default       |
|-------------------------------|----------------------------------------|---------------|
| `DATABASE_URL`                | URL de conexão com PostgreSQL          | —             |
| `RABBITMQ_URL`                | URL de conexão com RabbitMQ            | —             |
| `JWT_SECRET_KEY`              | Chave secreta JWT (≥32 caracteres)     | *obrigatório* |
| `JWT_ALGORITHM`               | Algoritmo JWT                          | `HS256`       |
| `S3_ENDPOINT`                 | Endpoint MinIO/S3                      | —             |
| `S3_ACCESS_KEY`               | Access key do MinIO                    | —             |
| `S3_SECRET_KEY`               | Secret key do MinIO                    | —             |
| `S3_BUCKET_PRESCRIPTIONS`     | Bucket para prescrições                | —             |
| `APPOINTMENT_CANCEL_HOURS_MIN`| Horas mínimas para cancelamento        | 24            |

## Como validar o funcionamento

- acesse `http://localhost:8003/healthz`;
- teste o cadastro de uma consulta;
- confirme se o prontuário ou prescrição foi persistido corretamente;
- verifique os logs de eventos publicados no RabbitMQ.

## Testes

```bash
cd backend/clinical-service
pytest -q
```

## Documentação relacionada

- [Documentação técnica da etapa 5 (Clinical Service)](../../DOCUMENTATION/ETAPA_5_Clinical_Service_Fastapi_Production.md)
- [Modelo lógico do banco de dados](../../DOCUMENTATION/ETAPA_14_Modelo_Logico_Clinical_Service.md)
- [Arquitetura global do sistema](../../DOCUMENTATION/ETAPA_1_ARQUITETURA_GLOBAL.md)

## Observação final

Esse serviço é o centro operacional do atendimento. Ele transforma uma ação do mundo real em um registro confiável e reutilizável pelo restante do sistema.