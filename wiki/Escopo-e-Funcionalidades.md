# Escopo e Funcionalidades

**Propósito:** PROMPTUÁRIO é uma plataforma para gestão eletrônica de registros de saúde (EHR) destinada a clínicas e unidades de saúde, permitindo cadastro de pacientes, gestão de prontuários, agendamento, prescrições e relatórios. O sistema foi projetado seguindo princípios de privacidade e conformidade com a LGPD: controle de acesso, anonimização e direitos de portabilidade/exclusão.

## Requisitos Funcionais (RF)
| ID | Requisito |
|---|---|
| RF-001 | Login com email e senha (autenticação local) |
| RF-002 | Login social via OAuth (GitHub/Google) |
| RF-003 | RBAC com roles: ADMIN, DOCTOR, ATTENDANT, PATIENT |
| RF-004 | Cadastro, atualização e gestão de pacientes |
| RF-005 | Registro de alergias, vacinas e medicamentos contínuos |
| RF-006 | Agendamento de consultas com regra mínima de 24h |
| RF-007 | Criação e versão de prontuário eletrônico por consulta |
| RF-008 | Geração de prescrições médicas em PDF (assinatura digital opcional) |
| RF-009 | Solicitação, registro e tracking de exames laboratoriais |
| RF-010 | Análise clínica assistida por IA (checagem de interações, sugestão de hipóteses) |
| RF-011 | Geração de relatórios assíncronos (CSV, PDF) via Reporting Service |
| RF-012 | Logs de auditoria de operações de banco de dados |
| RF-013 | Interface para relatórios de auditoria (filtros por serviço/operação) |
| RF-014 | Backup automático dos bancos de dados (agendado) |
| RF-015 | Monitoramento com Prometheus + Grafana |
| RF-016 | Rastreamento distribuído com Jaeger (tracing) |
| RF-017 | Notificações via eventos assíncronos (RabbitMQ) |
| RF-018 | Anonimização de dados para análises (LGPD) |
| RF-019 | Exportação de dados do paciente (portabilidade LGPD) |
| RF-020 | Dashboard administrativo com métricas e gestão de jobs |

## Requisitos de Qualidade (RQ)
| ID | Requisito |
|---|---|
| RQ-001 | Disponibilidade alvo > 99% (healthchecks, restart policies) |
| RQ-002 | Autenticação JWT com expiração de 30 minutos |
| RQ-003 | Rate limiting: 300 req/min autenticado, 30 req/min anônimo |
| RQ-004 | Conformidade LGPD: anonimização, consentimento, direito ao esquecimento |
| RQ-005 | Auditoria imutável (append-only) de operações relevantes |
| RQ-006 | Backup com retenção padrão de 7 dias |
| RQ-007 | Tempo de resposta < 500ms para 95% das requisições sob carga normal |
| RQ-008 | Evolução contínua da cobertura de testes (unit/integration/smoke) |
