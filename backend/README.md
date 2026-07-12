# PROMPTUARIO

Sistema de prontuário eletrônico (EHR) distribuído construído com FastAPI, RabbitMQ, PostgreSQL, MongoDB, Redis e MinIO.

## Arquitetura

```
Internet → API Gateway :8000
             ├── IAM Service        :8001  (Auth, Usuários, Roles)
             ├── Patient Service    :8002  (Pacientes, Alergias, Vacinas)
             ├── Clinical Service   :8003  (Consultas, Prontuários, Prescrições)
             ├── AI Service         :8004  (Análise clínica com LLM)
             └── Reporting Service  :8005  (Relatórios assíncronos)
```

No `docker-compose.yml`, cada microserviço escuta em `8000` dentro do container e é exposto no host nas portas `8000` a `8005`. O endpoint de health padronizado é `/healthz`.

## Stack

| Camada       | Tecnologia                              |
|--------------|-----------------------------------------|
| API          | FastAPI 0.115 + Pydantic v2             |
| Runtime      | Python 3.12                             |
| Auth         | JWT (HS256) + Redis blacklist           |
| Mensageria   | RabbitMQ 3.13 (aio-pika)               |
| BD Relacional| PostgreSQL 15 (SQLAlchemy 2 async)      |
| BD Documentos| MongoDB 7 (Motor async)                 |
| Cache        | Redis 7                                 |
| Storage      | MinIO (S3-compatible)                   |
| Workers      | Celery 5 + Redis broker                 |
| Containers   | Docker + Docker Compose                 |

## Pré-requisitos

- Docker 26+
- Docker Compose 2+
- GNU Make

## Início rápido

```bash
# 1. Clone e entre no diretório
git clone <repo>
cd promptuario-backend

# 2. Configure variáveis de ambiente
cp .env.example .env
# Edite .env se necessário (JWT_SECRET_KEY, LLM_API_KEY)

# 3. Suba tudo
make up

# 4. Verifique saúde dos serviços
make health
```

### URLs disponíveis

| Serviço | URL |
|---------|-----|
| API Gateway Health | http://localhost:8000/healthz |
| API Gateway Health Aggregate | http://localhost:8000/healthz/services |
| API Gateway | http://localhost:8000 |
| API Gateway Docs | http://localhost:8000/docs |
| IAM Health | http://localhost:8001/healthz |
| IAM Docs | http://localhost:8001/docs |
| Patient Health | http://localhost:8002/healthz |
| Patient Docs | http://localhost:8002/docs |
| Clinical Health | http://localhost:8003/healthz |
| Clinical Docs | http://localhost:8003/docs |
| AI Health | http://localhost:8004/healthz |
| AI Docs | http://localhost:8004/docs |
| Reporting Health | http://localhost:8005/healthz |
| Reporting Docs | http://localhost:8005/docs |
| RabbitMQ Mgmt | http://localhost:15672 |
| MinIO Console | http://localhost:9001 |

**Credenciais padrão admin:** `admin@promptuario.health` / `Admin@12345`

## Fluxo de autenticação

**Bash/Sh:**
```bash
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@promptuario.health","password":"Admin@12345"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Use o token
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/users
```

**PowerShell:**
```powershell
# 1. Login
$response = curl -s -X POST http://localhost:8000/api/v1/auth/login `
  -H "Content-Type: application/json" `
  -d '{"email":"admin@promptuario.health","password":"Admin@12345"}'

$TOKEN = ($response | ConvertFrom-Json).access_token

# 2. Use o token
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/users
```

## Exemplos de uso

Os exemplos abaixo usam o Gateway em `http://localhost:8000` e seguem os mesmos prefixos expostos nos serviços internos.

### Criar paciente
```bash
curl -X POST http://localhost:8000/api/v1/patients \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "usr_abc123",
    "full_name": "Maria da Silva",
    "cpf": "123.456.789-00",
    "date_of_birth": "1985-03-22",
    "blood_type": "O+",
    "phone": "+55 84 99999-0000"
  }'
```

**PowerShell:**
```powershell
$body = @{
  user_id = "usr_abc123"
  full_name = "Maria da Silva"
  cpf = "123.456.789-00"
  date_of_birth = "1985-03-22"
  blood_type = "O+"
  phone = "+55 84 99999-0000"
} | ConvertTo-Json

curl -X POST http://localhost:8000/api/v1/patients `
  -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  -d $body
```

### Agendar consulta

**Bash:**
```bash
curl -X POST http://localhost:8000/api/v1/appointments \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "pat_def456",
    "doctor_id": "doc_jkl012",
    "scheduled_at": "2026-06-10T14:00:00Z",
    "appointment_type": "CONSULTATION",
    "specialty": "Clínica Geral"
  }'
```

**PowerShell:**
```powershell
$body = @{
  patient_id = "pat_def456"
  doctor_id = "doc_jkl012"
  scheduled_at = "2026-06-10T14:00:00Z"
  appointment_type = "CONSULTATION"
  specialty = "Clínica Geral"
} | ConvertTo-Json

curl -X POST http://localhost:8000/api/v1/appointments `
  -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  -d $body
```

### Criar prontuário (médico)

**Bash:**
```bash
curl -X POST http://localhost:8000/api/v1/records \
  -H "Authorization: Bearer $TOKEN_DOCTOR" \
  -H "Content-Type: application/json" \
  -d '{
    "appointment_id": "appt_ghi789",
    "chief_complaint": "Dor de cabeça persistente há 3 dias",
    "anamnesis": "Paciente refere cefaleia bilateral pulsátil...",
    "diagnosis": "Enxaqueca sem aura",
    "diagnosis_codes": ["G43.009"],
    "treatment_plan": "Analgésicos + repouso"
  }'
```

**PowerShell:**
```powershell
$body = @{
  appointment_id = "appt_ghi789"
  chief_complaint = "Dor de cabeça persistente há 3 dias"
  anamnesis = "Paciente refere cefaleia bilateral pulsátil..."
  diagnosis = "Enxaqueca sem aura"
  diagnosis_codes = @("G43.009")
  treatment_plan = "Analgésicos + repouso"
} | ConvertTo-Json

curl -X POST http://localhost:8000/api/v1/records `
  -H "Authorization: Bearer $TOKEN_DOCTOR" `
  -H "Content-Type: application/json" `
  -d $body
```

### Solicitar análise de IA

**Bash:**
```bash
curl -X POST http://localhost:8000/api/v1/ai/analyze \
  -H "Authorization: Bearer $TOKEN_DOCTOR" \
  -H "Content-Type: application/json" \
  -d '{
    "analysis_type": "DRUG_INTERACTION_CHECK",
    "patient_id": "pat_def456",
    "record_id": "rec_mno345",
    "context": {
      "medications": [
        {"name": "Dipirona", "dosage": "500mg"},
        {"name": "Ibuprofeno", "dosage": "400mg"}
      ],
      "allergies": []
    }
  }'
```

**PowerShell:**
```powershell
$body = @{
  analysis_type = "DRUG_INTERACTION_CHECK"
  patient_id = "pat_def456"
  record_id = "rec_mno345"
  context = @{
    medications = @(
      @{ name = "Dipirona"; dosage = "500mg" },
      @{ name = "Ibuprofeno"; dosage = "400mg" }
    )
    allergies = @()
  }
} | ConvertTo-Json -Depth 3

curl -X POST http://localhost:8000/api/v1/ai/analyze `
  -H "Authorization: Bearer $TOKEN_DOCTOR" `
  -H "Content-Type: application/json" `
  -d $body
```

### Gerar relatório

**Bash:**
```bash
# Solicitar relatório
JOB=$(curl -s -X POST http://localhost:8000/api/v1/reports/export \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"report_type": "CONSULTATIONS", "output_format": "CSV", "parameters": {"from_date": "2026-01-01"}}')

JOB_ID=$(echo $JOB | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")

# Aguardar conclusão e baixar
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/reports/export/$JOB_ID/download
```

**PowerShell:**
```powershell
# Solicitar relatório
$body = @{
  report_type = "CONSULTATIONS"
  output_format = "CSV"
  parameters = @{ from_date = "2026-01-01" }
} | ConvertTo-Json

$response = curl -s -X POST http://localhost:8000/api/v1/reports/export `
  -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  -d $body

$JOB_ID = ($response | ConvertFrom-Json).job_id

# Aguardar conclusão e baixar
curl -H "Authorization: Bearer $TOKEN" `
  "http://localhost:8000/api/v1/reports/export/$JOB_ID/download"
```

## Roles e Permissões

| Funcionalidade           | PATIENT | ATTENDANT | DOCTOR | ADMIN |
|--------------------------|:-------:|:---------:|:------:|:-----:|
| Ver próprias consultas   | ✅      | —         | —      | ✅    |
| Listar todas consultas   | ❌      | ✅        | ✅     | ✅    |
| Agendar consulta         | ✅      | ✅        | ❌     | ✅    |
| Cancelar consulta        | ✅*     | ✅        | ✅     | ✅    |
| Criar prontuário         | ❌      | ❌        | ✅     | ❌    |
| Ver próprio prontuário   | ✅      | ❌        | —      | ✅    |
| Gerar prescrição         | ❌      | ❌        | ✅     | ❌    |
| Análise de IA            | ❌      | ❌        | ✅     | ✅    |
| Relatórios               | ❌      | ❌        | ✅†    | ✅    |
| Gerenciar usuários       | ❌      | ❌        | ❌     | ✅    |

`*` Regra de 24h de antecedência  
`†` Apenas próprios relatórios

## Estrutura do projeto

```
promptuario-backend/
├── docker-compose.yml
├── Makefile
├── .env.example
├── shared/                    # Biblioteca compartilhada
│   ├── events/                # Domain events + RabbitMQ broker
│   ├── models/                # SQLAlchemy base + session factory
│   ├── middleware/            # FastAPI auth dependency
│   └── utils/                 # JWT, hashing
├── gateway/                   # API Gateway (porta 8000)
│   └── app/main.py
├── iam-service/               # IAM Service (porta 8001)
│   ├── app/
│   │   ├── api/routers.py
│   │   ├── config.py
│   │   ├── domain/
│   │   └── infrastructure/
│   └── tests/
├── patient-service/           # Patient Service (porta 8002)
├── clinical-service/          # Clinical Service (porta 8003)
├── ai-service/                # AI Service (porta 8004)
└── reporting-service/         # Reporting Service (porta 8005)
    ├── app/workers/           # Celery tasks
    └── Dockerfile.worker
```

## Eventos de domínio (RabbitMQ)

| Evento                  | Exchange                 | Publisher     | Consumers                        |
|-------------------------|--------------------------|---------------|----------------------------------|
| `UserCreated`           | `promptuario.iam`        | IAM           | Patient, Clinical                |
| `UserDeactivated`       | `promptuario.iam`        | IAM           | Patient, Clinical                |
| `PatientCreated`        | `promptuario.patient`    | Patient       | Clinical (projection), Reporting |
| `PatientUpdated`        | `promptuario.patient`    | Patient       | Clinical (projection)            |
| `AllergyAdded`          | `promptuario.patient`    | Patient       | AI                               |
| `AppointmentCreated`    | `promptuario.clinical`   | Clinical      | Reporting                        |
| `AppointmentCancelled`  | `promptuario.clinical`   | Clinical      | Reporting                        |
| `MedicalRecordCreated`  | `promptuario.clinical`   | Clinical      | AI (auto-análise), Reporting     |
| `PrescriptionGenerated` | `promptuario.clinical`   | Clinical      | AI (drug check)                  |
| `AnalysisCompleted`     | `promptuario.ai`         | AI            | Clinical (attach result)         |

## Testes

**Bash/Make:**
```bash
# Todos os testes
make test

# Serviço específico
make test-svc SVC=iam-service

# Com coverage
cd iam-service && pytest tests/ --cov=app --cov-report=html
```

**PowerShell:**
```powershell
# Todos os testes (se Makefile disponível via WSL/Git Bash)
make test

# Alternativa direta em PowerShell - executar pytest em todos os serviços
Get-ChildItem -Filter "tests" -Recurse -Directory | ForEach-Object {
  $servicePath = Split-Path $_.FullName -Parent
  Push-Location $servicePath
  pytest tests/
  Pop-Location
}

# Serviço específico
Set-Location iam-service
pytest tests/ --cov=app --cov-report=html
Set-Location ..
```

## Desenvolvimento local

**Bash:**
```bash
# 1. Suba apenas a infraestrutura
make infra-up

# 2. Instale dependências localmente
cd iam-service && pip install -r requirements.txt
pip install -e ../shared  # se usar como pacote

# 3. Execute com reload automático
PYTHONPATH=.. uvicorn app.main:app --reload --port 8001
```

**PowerShell:**
```powershell
# 1. Suba apenas a infraestrutura
make infra-up

# 2. Instale dependências localmente
Set-Location iam-service
pip install -r requirements.txt
pip install -e ../shared
Set-Location ..

# 3. Execute com reload automático
$env:PYTHONPATH = ".."
uvicorn app.main:app --reload --port 8001
```

## Variáveis de ambiente importantes

| Variável                 | Descrição                              | Default                    |
|--------------------------|----------------------------------------|----------------------------|
| `JWT_SECRET_KEY`         | Chave secreta JWT (≥32 chars)          | *obrigatório em produção*  |
| `LLM_API_KEY`            | OpenAI API key (opcional)              | vazio (modo simulado)      |
| `LLM_MODEL`              | Modelo LLM a utilizar                  | `gpt-4o-mini`              |
| `FIRST_ADMIN_EMAIL`      | Email do admin inicial                 | `admin@promptuario.health` |
| `FIRST_ADMIN_PASSWORD`   | Senha do admin inicial                 | `Admin@12345`              |

> ⚠️ Altere `JWT_SECRET_KEY` e `FIRST_ADMIN_PASSWORD` **obrigatoriamente** em produção.

## Conformidade LGPD

- PII armazenada apenas no Patient Service
- Outros serviços armazenam apenas `patient_id`
- Endpoint de anonimização disponível (`DELETE /api/v1/patients/{id}`)
- Audit trail imutável em `MedicalRecordHistory`
- Tokens JWT com blacklist via Redis

## Backup operacional e recuperação

O ambiente já inclui um serviço dedicado de backup automático que:
- cria dumps do PostgreSQL e do MongoDB;
- grava artefatos em um volume persistente em `/var/backups`;
- envia cópias para o MinIO no bucket `backups`;
- registra o status da última execução em `status.json`.

### Execução manual

```bash
make backup-once
```

### Execução agendada

O serviço `backup-service` roda em modo agendado no `docker-compose.yml` e executa backups a cada 24h por padrão. Ajuste `BACKUP_SCHEDULE_HOURS` se precisar de outra periodicidade.

### Restore controlado

```bash
# PostgreSQL
make restore-db FILE=/var/backups/postgresql/iam_db/2026/07/11/postgres_iam_db_20260711_120000.sql.gz TARGET=iam_db

# MongoDB
make restore-mongo FILE=/var/backups/mongodb/ai_db/2026/07/11/mongo_ai_db_20260711_120000.archive.gz TARGET=ai_db
```

### Verificação básica

```bash
make status
docker compose logs backup-service --tail=100
```

> Se um backup individual falhar, o restante do ciclo continua e o serviço registra a falha sem derrubar os demais containers.

## Documentação relacionada

### Arquitetura e visão geral

- [Arquitetura de Software](../DOCUMENTATION/ARQUITETURA_DE_SOFTWARE.md) — Visão geral da arquitetura, padrões e decisões técnicas
- [Arquitetura Global](../DOCUMENTATION/ETAPA_1_ARQUITETURA_GLOBAL.md) — Diagramas de componentes, fluxos e comunicação entre serviços
- [Diagrama de Visão Funcional](../DOCUMENTATION/DIAGRAMA_DE_VISAO_FUNCIONAL_DO_SISTEMA.md) — Mapa funcional do sistema
- [Diagrama de Casos de Uso](../DOCUMENTATION/DIAGRAMA_DE_CASOS_DE_USO.md) — Casos de uso por ator do sistema

### Microserviços

- [IAM Service](../DOCUMENTATION/ETAPA_3_Iam_Service_Fastapi_Production.md) — Autenticação, autorização e gestão de usuários
- [Patient Service](../DOCUMENTATION/ETAPA_4_Patient_Service_Fastapi_Clean_Architecture.md) — Cadastro de pacientes, alergias, vacinas
- [Clinical Service](../DOCUMENTATION/ETAPA_5_Clinical_Service_Fastapi_Production.md) — Consultas, prontuários e prescrições
- [AI Service](../DOCUMENTATION/ETAPA_6_Ai_Service_Fastapi_Async_Clean_Architecture.md) — Análise clínica com IA
- [Reporting Service](../DOCUMENTATION/ETAPA_7_Reporting_Service_Fastapi_Production.md) — Relatórios e exportações assíncronas
- [API Gateway](../DOCUMENTATION/ETAPA_8_Api_Gateway_Fastapi_Production.md) — Roteamento, autenticação e agregação

### Infraestrutura e operações

- [Infraestrutura Distribuída (Docker)](../DOCUMENTATION/ETAPA_10_Infraestrutura_Distribuida_Docker_Rabbitmq_Postgresql.md) — Orquestração com Docker Compose, volumes e redes
- [Eventos e Mensageria (RabbitMQ)](../DOCUMENTATION/ETAPA_2_Eventos_Rabbitmq%20_Arquitetura_Event_Driven.md) — Arquitetura orientada a eventos
- [Observabilidade](../DOCUMENTATION/ETAPA_11_Observabilidade_Distribuida_Prometheus_Grafana_Loki.md) — Prometheus, Grafana, Loki e Jaeger
- [CI/CD](../DOCUMENTATION/ETAPA_12_Cicd_Distribuido_Github_Actions_Docker.md) — Pipeline de integração contínua com GitHub Actions
- [Backup e Restore](../DOCUMENTATION/OPERACIONAL_BACKUP_RESTORE.md) — Procedimentos operacionais de backup e recuperação

### Modelos de dados

- [Modelo Lógico do Banco de Dados](../DOCUMENTATION/ETAPA_14_Modelo_Logico_Do_Banco_De_Dados.md) — Visão geral dos modelos relacionais
- [Modelo Lógico IAM Service](../DOCUMENTATION/ETAPA_14_Modelo_Logico_IAM_Service.md) — Tabelas de usuários, roles e permissões
- [Modelo Lógico Patient Service](../DOCUMENTATION/ETAPA_14_Modelo_Logico_Patient_Service.md) — Tabelas de pacientes, alergias e vacinas
- [Modelo Lógico Clinical Service](../DOCUMENTATION/ETAPA_14_Modelo_Logico_Clinical_Service.md) — Tabelas de consultas, prontuários e prescrições
- [Modelo Lógico AI Service](../DOCUMENTATION/ETAPA_14_Modelo_Logico_AI_Service.md) — Coleções do MongoDB para análises
- [Modelo Lógico Reporting Service](../DOCUMENTATION/ETAPA_14_Modelo_Logico_Reporting_Service.md) — Tabelas de jobs e estatísticas

### Planejamento e requisitos

- [Requisitos e Histórias de Usuário](../DOCUMENTATION/REQUISITOS_HISTORIAS_DE_USUARIOS.md) — Funcionalidades detalhadas por papel de usuário
- [Planejamento de Endpoints](../DOCUMENTATION/PLANEJAMENTO_DE_ENDPOINTS_PI.md) — Mapeamento completo de rotas da API
- [Processo de Software](../DOCUMENTATION/ETAPA_13_Definicao_Do_Processo_De_Software.md) — Metodologia, sprints e práticas de desenvolvimento
- [Logs de Auditoria](../DOCUMENTATION/ETAPA_15_Planejamento_De_Logs_De_Auditoria.md) — Estratégia de auditoria e rastreabilidade
- [Status Geral do Sistema](../DOCUMENTATION/STATUS_GERAL_DO_SISTEMA.md) — Acompanhamento do progresso de implementação

## Contribuindo

1. Fork do repositório
2. Crie uma branch: `git checkout -b feature/minha-feature`
3. Commit: `git commit -m 'feat: adiciona X'`
4. Push: `git push origin feature/minha-feature`
5. Abra um Pull Request
