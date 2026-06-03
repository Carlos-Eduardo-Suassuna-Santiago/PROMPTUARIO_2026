# CI/CD Setup - PROMPTUARIO_2026

Este documento descreve os templates de CI/CD adicionados ao repositório e como usá-los.

## Arquivos gerados

- [`.github/workflows/ci-service.yml`](.github/workflows/ci-service.yml) — workflow genérico para serviços Python/FastAPI: lint, type-check, testes, build de imagem e scan.
- [`ci/smoke_test_runner.py`](ci/smoke_test_runner.py) — runner simples para executar o script de smoke tests presente em `backend/scripts/fastapi_services_smoke.py`.

## Variáveis de ambiente e Secrets necessários

Configurar os seguintes `secrets` no provedor (GitHub Actions):

- `DOCKER_REGISTRY_USER` — usuário do registry (opcional).
- `DOCKER_REGISTRY_TOKEN` — token/password para publicar imagens.
- `DOCKER_REGISTRY_HOST` — host do registry (ex: `ghcr.io/owner` ou `docker.io/owner`).
- `TRIVY_TOKEN` — token para scanner de imagem (opcional), ou instale trivy no runner.

Notas adicionais:
- `PYTHON_VERSION` é definido no workflow; atualize conforme necessário.

## Como usar localmente

Para reproduzir os passos do workflow localmente (testes e lint):

```powershell
python -m pip install -r backend/requirements.txt
pip install ruff mypy pytest pytest-cov
ruff check backend
mypy backend
pytest backend -q
```

Para executar o smoke runner localmente:

```powershell
python ci\smoke_test_runner.py
```

## Recomendações

- Centralizar dev-requirements em `backend/requirements-dev.txt` para acelerar CI.
- Configurar `branch protection` em `main` exigindo os checks `test-and-lint` e `build-image`.
- Adicionar um job extra de `deploy-to-staging` que só roda em `main` com imagens aprovadas.

## Próximos passos

- Gerar templates específicos por serviço em `backend/<service>/.github/workflows/ci.yml` caso cada serviço possua dependências distintas.
- Integrar upload de SBOM e relatórios de scanner como artefatos do workflow.

---

Documento gerado automaticamente pelo assistente. Ajuste o conteúdo conforme ambiente de registro e políticas internas.
