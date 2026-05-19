# ETAPA 14.5 — AI SERVICE

Este documento descreve o modelo lógico do AI Service. A persistência é feita em MongoDB para acomodar payloads e respostas mais flexíveis.

## Coleção

### analysis_jobs

A coleção principal do AI Service é `analysis_jobs`.

| Campo | Tipo | Nulo | Descrição |
|------|------|------|------|
| _id | string | Não | Identificador do job |
| analysis_type | string | Não | Tipo de análise solicitada |
| patient_id | string | Não | Paciente analisado |
| record_id | string | Sim | Prontuário de origem |
| context | object | Não | Payload contextual da análise |
| status | string | Não | PENDING, RUNNING, COMPLETED, FAILED |
| result | object | Sim | Resultado da IA |
| risk_level | string | Sim | Nível de risco retornado |
| model_version | string | Não | Versão do modelo usado |
| created_at | string/datetime ISO | Não | Data da criação |
| completed_at | string/datetime ISO | Sim | Data da conclusão |
| error | string | Sim | Mensagem de erro em falhas |

## Relacionamentos lógicos

- `record_id` referencia logicamente `medical_records.id` do Clinical Service.
- `patient_id` referencia logicamente `patients.id` do Patient Service.