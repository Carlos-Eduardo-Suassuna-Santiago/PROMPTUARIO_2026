# CI/CD Setup - PROMPTUARIO_2026

**Data:** 15 de julho de 2026  
**Status:** ✅ **Completamente operacional**

---

## 📋 Workflows Implementados

O pipeline de CI/CD do PROMPTUARIO utiliza **GitHub Actions** com 4 workflows principais:

| Workflow | Arquivo | Evento | Ações |
|----------|---------|--------|-------|
| **Backend CI** | `.github/workflows/backend-ci.yml` | Push/PR em `backend/` | Lint (ruff) + Testes (pytest) em 6 serviços |
| **Frontend CI** | `.github/workflows/frontend-ci.yml` | Push/PR em `frontend/` | Lint + Testes (vitest) + Build |
| **Docker Build** | `.github/workflows/docker-build.yml` | Push em `main` ou `developer` | Build + Push para GitHub Container Registry (GHCR) |
| **Deploy** | `.github/workflows/deploy.yml` | Push em `main` | Deploy via SSH para servidor de produção |

---

## 🔧 Workflow: Backend CI

**Arquivo:** `.github/workflows/backend-ci.yml`

```yaml
name: Backend CI

on:
  push:
    paths: ['backend/**']
  pull_request:
    paths: ['backend/**']
```

### Jobs

1. **Lint** (matrix: 6 serviços)
   - Executa `ruff check` em cada serviço
   
2. **Tests** (matrix: 6 serviços)
   - Executa `pytest` com cobertura
   - Gera relatório XML de coverage
   - Faz upload como artefato

### Serviços na matrix
```
iam-service, patient-service, clinical-service, ai-service, reporting-service, gateway
```

### Dependências
- Python 3.12
- ruff 0.6.8
- pytest 8.3.2 + pytest-asyncio + pytest-cov

---

## 🐳 Workflow: Docker Build & Publish

**Arquivo:** `.github/workflows/docker-build.yml`

```yaml
name: Docker Build & Publish

on:
  push:
    branches: [main, developer]
```

### Jobs

1. **docker-build** (matrix: 6 serviços backend)
   - Build multi-plataforma com BuildKit
   - Push para `ghcr.io/<owner>/promptuario-<service>:latest`
   - Push para `ghcr.io/<owner>/promptuario-<service>:<commit-sha>`
   - Cache de camadas via GitHub Actions

2. **docker-build-frontend**
   - Build do frontend React
   - Injeta `VITE_API_BASE_URL` via build-args
   - Push para `ghcr.io/<owner>/promptuario-frontend:latest`

### Registry
```
ghcr.io/<organization>/promptuario-iam-service
ghcr.io/<organization>/promptuario-patient-service
ghcr.io/<organization>/promptuario-clinical-service
ghcr.io/<organization>/promptuario-ai-service
ghcr.io/<organization>/promptuario-reporting-service
ghcr.io/<organization>/promptuario-gateway
ghcr.io/<organization>/promptuario-frontend
```

---

## 🚀 Workflow: Deploy

**Arquivo:** `.github/workflows/deploy.yml`

```yaml
name: Deploy

on:
  push:
    branches: [main]
```

Realiza deploy automático via SSH no servidor de produção:
```bash
cd PROMPTUARIO_2026
git pull origin main
cd backend
docker compose up --build -d
```

### Secrets Necessários

| Secret | Descrição |
|--------|-----------|
| `SERVER_HOST_BACKEND` | IP/DNS do servidor de produção |
| `SERVER_USER_BACKEND` | Usuário SSH |
| `SERVER_SSH_KEY_BACKEND` | Chave privada SSH |
| `PROD_API_URL` | URL da API para build do frontend |

---

## 🧪 Smoke Test Runner

**Arquivo:** `ci/smoke_test_runner.py`

Runner simples utilizado pela CI para validar serviços em deploy:
```python
# Executa o script de smoke tests do backend
python backend/scripts/fastapi_services_smoke.py
```

---

## 📊 Cobertura de Testes por Serviço

| Serviço | Test Files | Frameworks |
|---------|-----------|------------|
| **IAM** | `test_auth.py`, `test_auth_fastapi.py` | pytest + pytest-asyncio |
| **Patient** | `test_patient.py`, `test_documents.py`, `test_medication_history.py` | pytest |
| **Clinical** | `test_clinical.py`, `test_prescription_pdf.py`, `test_rich_notes_and_signature.py` | pytest |
| **AI** | `test_ai_service.py`, `test_llm_client.py`, `test_schemas.py`, `test_ai_integration_existing_db.py` | pytest |
| **Reporting** | `test_schemas.py`, `test_xlsx_builder.py` | pytest |
| **Gateway** | `test_gateway_resilience.py` | pytest |

---

## 🔒 Boas Práticas Implementadas

- ✅ **Concorrência**: Workflows com `concurrency` para cancelar execuções duplicadas
- ✅ **Cache**: Cache de dependências Python (pip) e camadas Docker (BuildKit)
- ✅ **Matrix Strategy**: Execução paralela por serviço
- ✅ **Artefatos**: Upload de relatórios de cobertura
- ✅ **Isolamento de Paths**: Workflows disparam apenas quando `backend/**` ou `frontend/**` são alterados
- ✅ **Branch Protection**: (recomendado) Exigir checks passando em `main`

---

## 📝 Recomendações

1. Configurar **branch protection** em `main` exigindo os checks dos workflows
2. Adicionar **job de staging** antes do deploy em produção
3. Integrar **scanner de vulnerabilidades** (Trivy) nas imagens Docker
4. Configurar **notificações** (Slack/Discord) para falhas no CI/CD

---

## 🔄 Fluxo Completo

```
Desenvolvedor faz push → GitHub Actions detecta mudanças
    ↓
   [Backend CI] Lint + Tests
    ↓
   [Docker Build] Build + Push para GHCR
    ↓
   [Deploy] (apenas main) SSH → git pull → docker compose up -d
    ↓
   [Smoke Tests] Valida serviços em funcionamento
```

---

**Documento Gerado:** 15 de julho de 2026  
**Versão:** 1.1.0  
**Responsável:** Equipe de Engenharia PROMPTUARIO