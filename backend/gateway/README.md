# PROMPTUARIO — API Gateway

O API Gateway é a porta de entrada do sistema. Ele recebe as chamadas externas e as direciona para o microsserviço correto, como um controlador central do fluxo de comunicação.

## Contexto no ecossistema Promptuário

```
Internet → API Gateway (:8000)
              ├── IAM Service        (:8001) — Auth, Usuários, Roles
              ├── Patient Service    (:8002) — Pacientes, Alergias, Vacinas
              ├── Clinical Service   (:8003) — Consultas, Prontuários, Prescrições
              ├── AI Service         (:8004) — Análise clínica com LLM
              └── Reporting Service  (:8005) — Relatórios assíncronos (Celery + S3)
```

O Gateway centraliza todas as requisições externas e roteia para o serviço correto. Ele é o único ponto de contato do cliente com o backend.

Porta padrão do serviço: `8000`

## Para que serve

Esse serviço existe para simplificar o acesso ao sistema. Em vez de o cliente precisar conhecer vários endereços diferentes, ele conversa com um único ponto de entrada.

## Como funciona, passo a passo

1. O cliente envia uma requisição para o gateway.
2. O gateway valida se a pessoa está autenticada (via JWT + Redis blacklist).
3. Ele identifica qual microsserviço deve atender a chamada.
4. Encaminha a requisição para o serviço correto (IAM, Patient, Clinical, AI ou Reporting).
5. O resultado volta ao cliente de forma transparente.

## O que ele faz na prática

- autentica e autoriza acessos;
- protege a API contra excesso de requisições (rate limiting);
- encaminha rotas para os serviços corretos;
- centraliza o acesso a todas as funcionalidades;
- agrega health checks de todos os microsserviços;
- adiciona resiliência com circuit breaker, cache seletivo e compressão gzip.

## Stack técnica

| Camada       | Tecnologia                        |
|--------------|-----------------------------------|
| API          | FastAPI 0.115+ (Python assíncrono)|
| Cache        | Redis 7 (blacklist de tokens)     |
| HTTP Client  | httpx                             |
| Auth         | JWT (HS256)                       |

## Pré-requisitos

- Redis disponível
- os demais microsserviços em execução (IAM, Patient, Clinical, AI, Reporting)
- Python 3.11+

## Início rápido

### Desenvolvimento local (sem Docker)

```bash
cd backend/gateway
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Com Docker Compose (infraestrutura completa)

```bash
cd backend
docker-compose up --build gateway
```

## Endpoints principais

| Método | Endpoint                    | Descrição                                    |
|--------|-----------------------------|----------------------------------------------|
| GET    | `/healthz`                  | Status do gateway                            |
| GET    | `/healthz/services`         | Status agregado dos microsserviços           |
| POST   | `/api/v1/auth/login`        | Login centralizado (roteia para IAM)         |
| GET    | `/api/v1/users`             | Lista usuários (roteia para IAM)             |
| GET    | `/api/v1/patients`          | Lista pacientes (roteia para Patient)        |
| GET    | `/api/v1/records`           | Lista prontuários (roteia para Clinical)     |
| POST   | `/api/v1/ai/analyze`        | Solicita análise (roteia para AI)            |
| POST   | `/api/v1/reports/export`    | Solicita relatório (roteia para Reporting)   |

### URLs de documentação

| Serviço              | URL                                    |
|----------------------|----------------------------------------|
| API Gateway Docs     | `http://localhost:8000/docs`           |
| IAM Service Docs     | `http://localhost:8001/docs`           |
| Patient Service Docs | `http://localhost:8002/docs`           |
| Clinical Service Docs| `http://localhost:8003/docs`           |
| AI Service Docs      | `http://localhost:8004/docs`           |
| Reporting Service Docs| `http://localhost:8005/docs`          |
| RabbitMQ Mgmt        | `http://localhost:15672`               |
| MinIO Console        | `http://localhost:9001`                |

## Fluxo de autenticação

```bash
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@promptuario.health","password":"Admin@12345"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Use o token nas requisições
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/users
```

> **Credenciais padrão admin:** `admin@promptuario.health` / `Admin@12345`

## Exemplo de uso

```bash
curl http://localhost:8000/healthz
```

## Variáveis de ambiente importantes

| Variável                     | Descrição                              | Default       |
|------------------------------|----------------------------------------|---------------|
| `IAM_SERVICE_URL`            | URL do IAM Service                     | —             |
| `PATIENT_SERVICE_URL`        | URL do Patient Service                 | —             |
| `CLINICAL_SERVICE_URL`       | URL do Clinical Service                | —             |
| `AI_SERVICE_URL`             | URL do AI Service                      | —             |
| `REPORTING_SERVICE_URL`      | URL do Reporting Service               | —             |
| `JWT_SECRET_KEY`             | Chave secreta JWT (≥32 caracteres)     | *obrigatório* |
| `JWT_ALGORITHM`              | Algoritmo JWT                          | `HS256`       |
| `REDIS_URL`                  | URL de conexão com Redis               | —             |
| `RATE_LIMIT_ANON_PER_MINUTE` | Limite anônimo por minuto              | 30            |
| `RATE_LIMIT_AUTH_PER_MINUTE` | Limite autenticado por minuto          | 300           |
| `RATE_LIMIT_API_KEY_PER_MINUTE` | Limite por API key por minuto      | 120           |
| `CACHE_TTL_SECONDS`          | TTL do cache de respostas GET          | 60            |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | Falhas consecutivas para abrir o circuito | 3 |
| `CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS` | Tempo antes de tentar fechar o circuito novamente | 30 |

## Como validar o funcionamento

- acesse `http://localhost:8000/healthz`;
- verifique `http://localhost:8000/healthz/services` para status agregado;
- teste um login para confirmar o roteamento para IAM;
- use `Accept-Encoding: gzip` para confirmar compressão em respostas grandes;
- envie `X-Api-Key` em integrações externas para validar rate limiting complementar;
- consulte a documentação interativa em `http://localhost:8000/docs`.

## Comportamento esperado

- Um downstream indisponível não derruba o gateway inteiro: o circuit breaker abre e devolve `503` com cabeçalho `X-Circuit-Breaker: open`.
- Rotas GET seletivamente cacheáveis retornam respostas consistentes por até `CACHE_TTL_SECONDS` segundos.
- Respostas grandes com `Accept-Encoding: gzip` são compactadas sem afetar autenticação ou conteúdo binário.
- O rate limiting por API key é opcional e complementar ao JWT, sem substituir a autenticação do usuário.

## Testes

```bash
cd backend/gateway
pytest -q
```

## Documentação relacionada

- [Documentação técnica da etapa 8 (API Gateway)](../../DOCUMENTATION/ETAPA_8_Api_Gateway_Fastapi_Production.md)
- [Arquitetura global do sistema](../../DOCUMENTATION/ETAPA_1_ARQUITETURA_GLOBAL.md)
- [Planejamento de endpoints](../../DOCUMENTATION/PLANEJAMENTO_DE_ENDPOINTS_PI.md)

## Observação final

O gateway é a camada de entrada do sistema. Ele organiza o tráfego e permite que a arquitetura fique modular e mais simples de manter.