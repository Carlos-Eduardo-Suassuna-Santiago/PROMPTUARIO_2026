# PROMPTUARIO — AI Service

O AI Service é o módulo responsável por trazer inteligência ao prontuário eletrônico. Ele transforma dados clínicos em informações úteis para apoiar a análise médica, principalmente em cenários como identificação de interações medicamentosas, resumos clínicos e avaliação de sintomas.

## Contexto no ecossistema Promptuário

```
Gateway (:8000) → AI Service (:8004) → MongoDB / Redis / RabbitMQ
                    │
                    └── processa análises assíncronas e consome eventos do sistema
```

O AI Service está posicionado atrás do **API Gateway** e se comunica com:
- **MongoDB** — armazenamento de análises e resultados
- **Redis** — cache de jobs e filas
- **RabbitMQ** — publicação de eventos (`AnalysisCompleted`) e consumo de eventos (`MedicalRecordCreated`, `PrescriptionGenerated`)

Porta padrão do serviço: `8004`

## Para que serve

Este microsserviço existe para ajudar profissionais de saúde a trabalhar com mais suporte e menos esforço manual. Em vez de revisar tudo manualmente, o sistema pode analisar automaticamente informações já registradas e produzir um resultado útil.

## Como funciona, passo a passo

1. Um médico ou outro fluxo do sistema envia uma solicitação para análise via **Gateway**.
2. O serviço cria um **job de processamento** para acompanhar essa tarefa.
3. A análise é executada em segundo plano, sem travar a aplicação.
4. O resultado fica armazenado e pode ser consultado mais tarde.
5. O serviço também pode reagir automaticamente a eventos do sistema, como a criação de um prontuário (`MedicalRecordCreated`) ou de uma prescrição (`PrescriptionGenerated`), publicando o evento `AnalysisCompleted` ao final.

## O que ele faz na prática

- verifica possíveis interações entre medicamentos;
- auxilia na análise de sintomas;
- gera resumos clínicos a partir do contexto recebido;
- acompanha histórico de análises por prontuário.

## Stack técnica

| Camada       | Tecnologia                        |
|--------------|-----------------------------------|
| API          | FastAPI 0.115+ (Python assíncrono)|
| BD Documentos| MongoDB 7 (Motor async)           |
| Cache        | Redis 7                           |
| Mensageria   | RabbitMQ 3.13 (aio-pika)          |
| Validação    | Pydantic v2                       |

## Pré-requisitos

- Python 3.11+
- Redis disponível
- MongoDB disponível
- RabbitMQ disponível

## Início rápido

### Desenvolvimento local (sem Docker)

```bash
cd backend/ai-service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8004
```

### Com Docker Compose (infraestrutura completa)

```bash
cd backend
docker-compose up --build ai-service
```

## Endpoints principais

| Método | Endpoint                              | Descrição                          |
|--------|---------------------------------------|------------------------------------|
| POST   | `/api/v1/ai/analyze`                 | Cria uma nova análise assíncrona   |
| GET    | `/api/v1/ai/jobs/{job_id}`           | Consulta o status do job           |
| GET    | `/api/v1/ai/records/{record_id}/analyses` | Lista as análises de um prontuário |
| GET    | `/healthz`                           | Health check do serviço            |

## Eventos de domínio

| Evento                | Publica/Consome | Exchange               | Descrição                     |
|-----------------------|----------------|------------------------|-------------------------------|
| `MedicalRecordCreated`| Consome        | `promptuario.clinical` | Prontuário criado → auto-análise |
| `PrescriptionGenerated`| Consome       | `promptuario.clinical` | Prescrição gerada → drug check |
| `AllergyAdded`        | Consome        | `promptuario.patient`  | Alergia registrada → alerta   |
| `AnalysisCompleted`   | Publica        | `promptuario.ai`       | Análise finalizada            |

## Exemplo de uso

```bash
curl -X POST http://localhost:8000/api/v1/ai/analyze \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "analysis_type": "DRUG_INTERACTION_CHECK",
    "patient_id": "pat_123",
    "record_id": "rec_456",
    "context": {
      "medications": [{"name": "Dipirona", "dosage": "500mg"}],
      "allergies": []
    }
  }'
```

> **Nota:** O endpoint é acessado via **Gateway** (`:8000`), que faz o roteamento para o AI Service (`:8004`).

## Variáveis de ambiente importantes

| Variável          | Descrição                          | Default       |
|-------------------|------------------------------------|---------------|
| `MONGODB_URL`     | URL de conexão com MongoDB         | —             |
| `REDIS_URL`       | URL de conexão com Redis           | —             |
| `RABBITMQ_URL`    | URL de conexão com RabbitMQ        | —             |
| `JWT_SECRET_KEY`  | Chave secreta JWT (≥32 caracteres) | *obrigatório* |
| `JWT_ALGORITHM`   | Algoritmo JWT                      | `HS256`       |
| `LLM_API_KEY`     | OpenAI API key (opcional)          | vazio (modo simulado) |
| `LLM_MODEL`       | Modelo LLM a utilizar              | `gpt-4o-mini` |
| `LLM_MAX_TOKENS`  | Máximo de tokens por chamada       | 1024          |

## Como validar o funcionamento

- acesse `http://localhost:8004/healthz`;
- envie uma análise e observe o `job_id` retornado;
- consulte o status do job para acompanhar o processamento;
- verifique se o evento `AnalysisCompleted` foi publicado (logs do RabbitMQ).

## Testes

```bash
cd backend/ai-service
pytest -q
```

## Documentação relacionada

- [Documentação técnica da etapa 6 (AI Service)](../../DOCUMENTATION/ETAPA_6_Ai_Service_Fastapi_Async_Clean_Architecture.md)
- [Modelo lógico do banco de dados](../../DOCUMENTATION/ETAPA_14_Modelo_Logico_AI_Service.md)
- [Arquitetura global do sistema](../../DOCUMENTATION/ETAPA_1_ARQUITETURA_GLOBAL.md)

## Observação final

Esse serviço não substitui a avaliação clínica, mas funciona como um apoio inteligente que organiza informações e pode reduzir erros manuais em tarefas repetitivas.