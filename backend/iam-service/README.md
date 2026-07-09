# PROMPTUARIO — IAM Service

O IAM Service é o módulo responsável por autenticação, autorização e gestão de usuários. Ele decide quem pode entrar no sistema e quais ações cada pessoa pode realizar.

## Contexto no ecossistema Promptuário

```
Gateway (:8000) → IAM Service (:8001) → PostgreSQL / Redis / RabbitMQ
```

O IAM Service está posicionado atrás do **API Gateway** e se comunica com:
- **PostgreSQL** — persistência de usuários, roles e permissões
- **Redis** — blacklist de tokens JWT (logout) e cache de sessão
- **RabbitMQ** — publicação de eventos de domínio (`UserCreated`, `UserDeactivated`)

Porta padrão do serviço: `8001`

## Para que serve

Este microsserviço existe para proteger o sistema e garantir que apenas usuários autorizados tenham acesso às informações e funções corretas.

## Como funciona, passo a passo

1. O usuário envia e-mail e senha para fazer login.
2. O serviço valida as credenciais no banco de dados.
3. Se estiver tudo certo, ele gera um token JWT com as claims de role e permissões.
4. Esse token é usado nas próximas requisições para provar a identidade do usuário.
5. O serviço também define papéis como administrador, médico, atendente e paciente, cada um com permissões específicas.
6. Eventos como `UserCreated` e `UserDeactivated` são publicados no RabbitMQ para que outros serviços (Patient, Clinical) mantenham suas projeções atualizadas.

## O que ele faz na prática

- autentica usuários;
- gera e renova tokens (access + refresh);
- controla papéis e permissões;
- cria e consulta usuários;
- protege o sistema contra acessos indevidos;
- publica eventos de domínio para integração.

## Stack técnica

| Camada        | Tecnologia                        |
|---------------|-----------------------------------|
| API           | FastAPI 0.115+ (Python assíncrono)|
| BD Relacional | PostgreSQL 15 (SQLAlchemy 2 async)|
| Cache         | Redis 7 (blacklist de tokens)     |
| Mensageria    | RabbitMQ 3.13 (aio-pika)          |
| Auth          | JWT (HS256)                       |

## Pré-requisitos

- PostgreSQL disponível
- Redis disponível
- RabbitMQ disponível
- Python 3.11+

## Início rápido

### Desenvolvimento local (sem Docker)

```bash
cd backend/iam-service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

### Com Docker Compose (infraestrutura completa)

```bash
cd backend
docker-compose up --build iam-service
```

## Endpoints principais

| Método | Endpoint                    | Descrição                     |
|--------|-----------------------------|-------------------------------|
| POST   | `/api/v1/auth/login`        | Autenticação do usuário       |
| POST   | `/api/v1/auth/refresh`      | Renovação do token            |
| GET    | `/api/v1/users`             | Lista usuários                |
| POST   | `/api/v1/users`             | Cria um novo usuário          |
| GET    | `/healthz`                  | Health check do serviço       |

## Eventos de domínio

| Evento             | Publica/Consome | Exchange             | Descrição                     |
|--------------------|----------------|----------------------|-------------------------------|
| `UserCreated`      | Publica        | `promptuario.iam`    | Usuário cadastrado            |
| `UserDeactivated`  | Publica        | `promptuario.iam`    | Usuário desativado            |

## Roles e permissões

| Funcionalidade           | PATIENT | ATTENDANT | DOCTOR | ADMIN |
|--------------------------|:-------:|:---------:|:------:|:-----:|
| Ver próprias consultas   | ✅      | —         | —      | ✅    |
| Listar todas consultas   | ❌      | ✅        | ✅     | ✅    |
| Agendar consulta         | ✅      | ✅        | ❌     | ✅    |
| Cancelar consulta        | ✅*     | ✅        | ✅     | ✅    |
| Criar prontuário         | ❌      | ❌        | ✅     | ❌    |
| Ver próprio prontuário   | ✅      | ❌        | —      | ✅    |
| Gerar prescrição         | ❌      | ❌        | ✅     | ❌    |
| Análise de IA            | ❌      | ❌        | ✅     | ✅    |
| Relatórios               | ❌      | ❌        | ✅†    | ✅    |
| Gerenciar usuários       | ❌      | ❌        | ❌     | ✅    |

`*` Regra de 24h de antecedência  
`†` Apenas próprios relatórios

## Exemplo de uso

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@promptuario.health",
    "password": "Admin@12345"
  }'
```

> **Nota:** O endpoint é acessado via **Gateway** (`:8000`), que faz o roteamento para o IAM Service (`:8001`).

## Variáveis de ambiente importantes

| Variável                   | Descrição                              | Default                    |
|----------------------------|----------------------------------------|----------------------------|
| `DATABASE_URL`             | URL de conexão com PostgreSQL          | —                          |
| `REDIS_URL`                | URL de conexão com Redis               | —                          |
| `RABBITMQ_URL`             | URL de conexão com RabbitMQ            | —                          |
| `JWT_SECRET_KEY`           | Chave secreta JWT (≥32 caracteres)     | *obrigatório em produção*  |
| `JWT_ALGORITHM`            | Algoritmo JWT                          | `HS256`                    |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Expiração do access token (minutos) | 30                         |
| `REFRESH_TOKEN_EXPIRE_DAYS`   | Expiração do refresh token (dias)   | 7                          |
| `FIRST_ADMIN_EMAIL`        | Email do admin inicial                 | `admin@promptuario.health` |
| `FIRST_ADMIN_PASSWORD`     | Senha do admin inicial                 | `Admin@12345`              |
| `FIRST_ADMIN_NAME`         | Nome do admin inicial                  | `Admin`                    |

> ⚠️ Altere `JWT_SECRET_KEY` e `FIRST_ADMIN_PASSWORD` **obrigatoriamente** em produção.

## Como validar o funcionamento

- acesse `http://localhost:8001/healthz`;
- teste o login com as credenciais configuradas;
- confirme se o token é retornado corretamente;
- verifique se o evento `UserCreated` foi publicado (logs do RabbitMQ).

## Testes

```bash
cd backend/iam-service
pytest -q
```

## Documentação relacionada

- [Documentação técnica da etapa 3 (IAM Service)](../../DOCUMENTATION/ETAPA_3_Iam_Service_Fastapi_Production.md)
- [Modelo lógico do banco de dados](../../DOCUMENTATION/ETAPA_14_Modelo_Logico_IAM_Service.md)
- [Arquitetura global do sistema](../../DOCUMENTATION/ETAPA_1_ARQUITETURA_GLOBAL.md)

## Observação final

Esse serviço é a base da segurança do sistema. Sem ele, o restante da aplicação não teria como distinguir usuários e permissões.