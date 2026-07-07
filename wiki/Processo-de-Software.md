# Processo de Software

Metodologia: desenvolvimento incremental com entregas parciais e integração contínua, alinhado ao guia do Projeto Integrador do IFRN.

Entregas
- Entrega 01 (05–06/05/2026):
  - Documento de requisitos e histórias de usuário
  - Diagrama de casos de uso
  - Arquitetura de software inicial
  - Processo de software definido
  - Modelo lógico do banco de dados
  - Protótipo funcional e smoke tests
  - Planejamento de logs de auditoria

- Entrega 02 (pendente):
  - Produto concluído e testado
  - Manual de ambiente + Wiki completa
  - Arquitetura C4 finalizada
  - CI/CD funcional
  - Auditoria, monitoramento e backup implementados

Branches:
- `main` — código estável para entrega
- `developer` — desenvolvimento ativo
- `feature/*` — features isoladas (merge em `developer`)

Integrantes (exemplo — preencher com nomes reais):
- Nome 1 — backend / IAM
- Nome 2 — backend / Clinical & Reporting
- Nome 3 — AI / integração LLM
- Nome 4 — frontend / UX
- Nome 5 — DevOps / observabilidade & infra

Fluxo de trabalho:
- Trabalhe em `feature/*`, abra PR para `developer`.
- Revisões de PR, CI verde obrigatório antes de merge.
- Deploy de imagens a partir de `developer`/`main` via GitHub Actions para GHCR (se configurado).
