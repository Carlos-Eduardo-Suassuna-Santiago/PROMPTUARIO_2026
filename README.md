# Promptuário

[![CI Backend](https://github.com/Carlos-Eduardo-Suassuna-Santiago/PROMPTUARIO_2026/actions/workflows/backend-ci.yml/badge.svg?branch=main)](https://github.com/Carlos-Eduardo-Suassuna-Santiago/PROMPTUARIO_2026/actions/workflows/backend-ci.yml)


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

### Principais documentos

- [Arquitetura de Software](DOCUMENTATION/ARQUITETURA_DE_SOFTWARE.md) — Visão geral da arquitetura, padrões e decisões técnicas
- [Arquitetura Global](DOCUMENTATION/ETAPA_1_ARQUITETURA_GLOBAL.md) — Diagramas de componentes, fluxos e comunicação entre serviços
- [Eventos e Mensageria (RabbitMQ)](DOCUMENTATION/ETAPA_2_Eventos_Rabbitmq%20_Arquitetura_Event_Driven.md) — Arquitetura orientada a eventos e definição das exchanges
- [Infraestrutura Distribuída (Docker)](DOCUMENTATION/ETAPA_10_Infraestrutura_Distribuida_Docker_Rabbitmq_Postgresql.md) — Orquestração com Docker Compose, volumes e redes
- [Observabilidade](DOCUMENTATION/ETAPA_11_Observabilidade_Distribuida_Prometheus_Grafana_Loki.md) — Prometheus, Grafana, Loki e Jaeger
- [CI/CD](DOCUMENTATION/ETAPA_12_Cicd_Distribuido_Github_Actions_Docker.md) — Pipeline de integração contínua com GitHub Actions
- [Modelo Lógico do Banco de Dados](DOCUMENTATION/ETAPA_14_Modelo_Logico_Do_Banco_De_Dados.md) — Diagramas ER e modelos relacionais
- [Requisitos e Histórias de Usuário](DOCUMENTATION/REQUISITOS_HISTORIAS_DE_USUARIOS.md) — Funcionalidades detalhadas por papel de usuário
- [Planejamento de Endpoints](DOCUMENTATION/PLANEJAMENTO_DE_ENDPOINTS_PI.md) — Mapeamento completo de rotas da API
- [Status Geral do Sistema](DOCUMENTATION/STATUS_GERAL_DO_SISTEMA.md) — Acompanhamento do progresso de implementação
- [Processo de Software](DOCUMENTATION/ETAPA_13_Definicao_Do_Processo_De_Software.md) — Metodologia, sprints e práticas de desenvolvimento
- [Backup e Restore](DOCUMENTATION/OPERACIONAL_BACKUP_RESTORE.md) — Procedimentos operacionais de backup e recuperação

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
