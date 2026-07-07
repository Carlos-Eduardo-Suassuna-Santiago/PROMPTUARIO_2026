# PROMPTUÁRIO — Sistema EHR Distribuído

[![CI](https://github.com/Carlos-Eduardo-Suassuna-Santiago/PROMPTUARIO_2026/actions/workflows/ci-service.yml/badge.svg?branch=developer)](https://github.com/Carlos-Eduardo-Suassuna-Santiago/PROMPTUARIO_2026/actions)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

PROMPTUÁRIO é um sistema de prontuário eletrônico de saúde (EHR) projetado como um sistema distribuído baseado em microsserviços. O projeto foi desenvolvido como Trabalho de Conclusão/Projeto Integrador no IFRN — Campus Pau dos Ferros, com foco em arquitetura escalável, observabilidade e conformidade com requisitos legais (LGPD). O sistema cobre desde autenticação e gestão de usuários até criação de prontuários, suporte à análise clínica assistida por IA e geração de relatórios assíncronos.

A arquitetura adota FastAPI em Python 3.12, bancos relacionais PostgreSQL para dados críticos, MongoDB para dados de IA, RabbitMQ para troca de eventos, Redis para cache/filas Celery, MinIO para armazenamento compatível com S3, e um stack de observabilidade (Prometheus, Grafana, Jaeger). A implantação local é compatível com Docker Compose e os serviços são organizados por responsabilidades (gateway, iam, patient, clinical, ai, reporting).

A branch principal de desenvolvimento é `developer`. O repositório inclui documentação técnica extensa em DOCUMENTATION/, testes de smoke e pipelines de CI/CD. Este Wiki agrupa a documentação de uso, arquitetura, operações e políticas (auditoria/backup/monitoramento).

Links rápidos para as páginas do Wiki:
- [Escopo e Funcionalidades](Escopo-e-Funcionalidades.md)
- [Arquitetura C4](Arquitetura-C4.md)
- [Auditoria, Monitoramento & Backup](Auditoria-Monitoramento-Backup.md)
- [API Reference](API-Reference.md)
- [Manual de Ambiente](Manual-de-Ambiente.md)
- [CI/CD](CI-CD.md)
- [Processo de Software](Processo-de-Software.md)

Início rápido:
```bash
git clone https://github.com/Carlos-Eduardo-Suassuna-Santiago/PROMPTUARIO_2026.git
cp backend/.env.example backend/.env
cd backend && docker compose up -d
```

Documentação técnica (no repositório):
- DOCUMENTATION/ARQUITETURA_DE_SOFTWARE.md
- DOCUMENTATION/ETAPA_4_Patient_Service_Fastapi_Clean_Architecture.md
- DOCUMENTATION/ETAPA_6_Ai_Service_Fastapi_Async_Clean_Architecture.md
