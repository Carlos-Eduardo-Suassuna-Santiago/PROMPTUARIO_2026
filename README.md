# Promptuário

[![CI Backend](https://github.com/Carlos-Eduardo-Suassuna-Santiago/PROMPTUARIO_2026/actions/workflows/ci-service.yml/badge.svg?branch=developer)](https://github.com/Carlos-Eduardo-Suassuna-Santiago/PROMPTUARIO_2026/actions/workflows/ci-service.yml)

## Proposta do projeto

O Promptuário DSD é uma plataforma composta por microserviços para gerenciar dados clínicos, processamento por IA, autenticação/autorização e geração de relatórios. O objetivo é oferecer uma arquitetura desacoplada, escalável e observável para suportar fluxos de integração entre serviços clínicos, processamento assíncrono e relatórios.

## Funcionamento do sistema

Arquitetura principal (microserviços):

- `iam-service`: serviço de identidade e autorização (usuários, roles, tokens).
- `patient-service`: gerencia dados de pacientes e histórico clínico.
- `clinical-service`: manipula casos clínicos, registros e fluxos clínicos.
- `ai-service`: responsável por processamento assíncrono e modelos de IA.
- `reporting-service`: gera relatórios e exportações.
- `gateway`: API Gateway (roteamento, autenticação, agregação de endpoints).
- `shared`: código compartilhado (eventos, middleware, modelos, utilitários).

Comunicação e infraestrutura:

- Comunicação entre serviços via eventos (ex.: RabbitMQ) e HTTP/REST para chamadas síncronas.
- Persistência em cada serviço (Postgres/Migrations) quando aplicável.
- Orquestração para desenvolvimento e deploy via `docker-compose` e imagens Docker.
- Observabilidade com Prometheus/Grafana/Loki (conforme documentação em `DOCUMENTATION/`).

## Requisitos

- Python 3.10+ (recomendado)
- Docker & Docker Compose (para execução em container)
- Make (opcional, para atalhos de comandos)

## Executando localmente (modo desenvolvimento)

1. Crie e ative um ambiente virtual (Windows PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instale dependências do serviço que deseja executar (ex.: `ai-service`):

```powershell
cd promptuario-backend\ai-service
pip install -r requirements.txt
```

3. Execute o serviço (exemplo com FastAPI):

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

4. Cada serviço tem sua própria pasta com `requirements.txt`, `Dockerfile` e testes. Consulte `README.md` local de cada serviço quando existir.

## Executando com Docker Compose (integração completa)

1. No diretório raiz (onde está `docker-compose.yml` ou em `promptuario-backend`), suba os serviços:

```bash
cd promptuario-backend
docker-compose up --build
```

2. Para rodar em segundo plano:

```bash
docker-compose up -d --build
```

3. Para parar e remover containers:

```bash
docker-compose down
```

Observação: O repositório pode incluir múltiplos `docker-compose` (por serviço ou orquestração completa). Verifique o arquivo `docker-compose.yml` correto em `promptuario-backend/`.

## Banco de dados e migrações

- Cada serviço que usa banco de dados inclui uma pasta `migrations/`. Use as ferramentas de migração do respectivo serviço (por exemplo, Alembic para SQLAlchemy) para aplicar migrações localmente ou via container.

## Testes

Execute os testes por serviço:

```powershell
cd promptuario-backend\ai-service
pytest -q
```

## Scripts úteis

- `scripts/fastapi_services_smoke.py`: script para smoke tests dos serviços FastAPI.
- `scripts/insomnia_auth_smoke.py`: helper para testes de autenticação via Insomnia.

## Documentação

Documentação técnica, diagramas e planejamentos estão em `DOCUMENTATION/` e `DOCUMENTATION/DIAGRAMS/`. Consulte os arquivos para arquitetura, endpoints planejados e observabilidade.

## Contribuição

1. Abra uma issue descrevendo a mudança.
2. Crie um branch com a feature/bugfix.
3. Faça um PR apontando para a branch principal do repositório.
