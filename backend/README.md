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

## Contribuindo

1. Fork do repositório
2. Crie uma branch: `git checkout -b feature/minha-feature`
3. Commit: `git commit -m 'feat: adiciona X'`
4. Push: `git push origin feature/minha-feature`
5. Abra um Pull Request
