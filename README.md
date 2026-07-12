# Promptuário

[![CI Backend](https://github.com/Carlos-Eduardo-Suassuna-Santiago/PROMPTUARIO_2026/actions/workflows/ci-service.yml/badge.svg?branch=developer)](https://github.com/Carlos-Eduardo-Suassuna-Santiago/PROMPTUARIO_2026/actions/workflows/ci-service.yml)

## Proposta do projeto

O Promptuário DSD é uma plataforma composta por microserviços para gerenciar dados clínicos, processamento por IA, autenticação/autorização e geração de relatórios. O objetivo é oferecer uma arquitetura desacoplada, escalável e observável para suportar fluxos de integração entre serviços clínicos, processamento assíncrono e relatórios.

## Funcionamento do sistema

Arquitetura principal (microserviços):

- `iam-service`: serviço de identidade e autorização (usuários, roles, tokens, OAuth2 Google).
- `patient-service`: gerencia dados de pacientes e histórico clínico.
- `clinical-service`: manipula casos clínicos, registros e fluxos clínicos.
- `ai-service`: responsável por processamento assíncrono e modelos de IA.
- `reporting-service`: gera relatórios e exportações.
- `gateway`: API Gateway (roteamento, autenticação, agregação de endpoints).
- `shared`: código compartilhado (eventos, middleware, modelos, utilitários).

Comunicação e infraestrutura:

- Comunicação entre serviços via eventos (RabbitMQ) e HTTP/REST para chamadas síncronas.
- Persistência em cada serviço: PostgreSQL (4 bancos) + MongoDB (AI Service).
- Orquestração via `docker-compose` com 11+ serviços.
- Observabilidade com Prometheus/Grafana/Jaeger/OpenTelemetry/Loki.

## Requisitos

- Python 3.12+ (recomendado)
- Docker & Docker Compose (para execução em container)
- Make (opcional, para atalhos de comandos)

## Executando com Docker Compose (integração completa)

Na pasta `backend/`:

```bash
cd backend
docker compose up --build
```

Para rodar em segundo plano:

```bash
docker compose up -d --build
```

Para parar e remover containers:

```bash
docker compose down
```

## Executando localmente (modo desenvolvimento)

1. Crie e ative um ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instale dependências do serviço que deseja executar (ex.: `ai-service`):

```powershell
cd backend\ai-service
pip install -r requirements.txt
```

3. Execute o serviço:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

## Banco de dados e migrações

Cada serviço que usa banco de dados utiliza SQLAlchemy async com `create_all` no startup. Migrações com Alembic podem ser adicionadas conforme necessidade.

## Testes

Execute os testes por serviço:

```powershell
cd backend\ai-service
pytest -q
```

## Smoke tests

```powershell
cd backend
python scripts/fastapi_services_smoke.py
```

## Documentação

Documentação técnica, diagramas e planejamentos estão em `DOCUMENTATION/` e `DOCUMENTATION/DIAGRAMS/`.

## Estrutura do Projeto

```
PROMPTUARIO_2026/
├── backend/
│   ├── docker-compose.yml        # Orquestração completa
│   ├── Makefile                  # Comandos padronizados
│   ├── .env.example              # Template de variáveis
│   │
│   ├── iam-service/              # Porta 8001
│   ├── patient-service/          # Porta 8002
│   ├── clinical-service/         # Porta 8003
│   ├── ai-service/               # Porta 8004
│   ├── reporting-service/        # Porta 8005
│   ├── gateway/                  # Porta 8000
│   ├── shared/                   # Código compartilhado
│   ├── backup/                   # Serviço de backup
│   ├── observability/            # Configs Prometheus/Grafana
│   └── scripts/                  # Scripts utilitários
│
├── promptuario-frontend/         # Frontend React + TypeScript
├── ci/                           # CI/CD helpers
└── DOCUMENTATION/                # Documentação técnica
```

## Contribuição

1. Abra uma issue descrevendo a mudança.
2. Crie um branch com a feature/bugfix.
3. Faça um PR apontando para a branch principal do repositório.