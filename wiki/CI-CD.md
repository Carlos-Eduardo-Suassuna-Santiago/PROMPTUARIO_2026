# CI / CD

O pipeline principal está definido em `.github/workflows/ci-service.yml` e executa lint, testes, smoke-tests e build/push de imagens.

Jobs:
1. `lint` — executa `ruff` em cada serviço (matrix por serviço)
2. `tests` — executa `pytest` nas pastas de testes (iam, patient, clinical) com matrix
3. `smoke-tests` — sobe stack mínima (docker compose), aguarda health e executa scripts de smoke em `scripts/`
4. `build-images` — `docker buildx` e push para `ghcr.io` (executado em push para `developer`/`main`)

Triggers:
- `push` para branches `developer` ou `main`
- `pull_request` para `developer` ou `main`

Como ver resultados:
GitHub → Actions → selecionar workflow "CI — PROMPTUÁRIO Backend"

Imagens geradas (exemplo):
- `ghcr.io/Carlos-Eduardo-Suassuna-Santiago/promptuario-iam-service:<commit-sha>`
- `ghcr.io/Carlos-Eduardo-Suassuna-Santiago/promptuario-iam-service:latest`
(igual para cada serviço: patient, clinical, ai, reporting, gateway, promptuario-frontend)

Adicionar novo serviço ao CI:
- Atualizar `matrix.service` em jobs `lint` e `build-images`
- Adicionar entradas de testes se necessário (job `tests`)
