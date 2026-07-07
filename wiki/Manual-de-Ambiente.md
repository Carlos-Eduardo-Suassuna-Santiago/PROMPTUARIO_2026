# Manual de Ambiente

## Pré-requisitos
- Docker 26+ e Docker Compose 2+
- GNU Make
- Git
- (Opcional) `psql`, `mongorestore`, `aws-cli` (para testes locais de backup)

Passo a passo (6 passos):
1. Clone o repositório e entre na pasta:
```bash
git clone https://github.com/Carlos-Eduardo-Suassuna-Santiago/PROMPTUARIO_2026.git
cd PROMPTUARIO_2026
```
2. Copie o arquivo de ambiente:
```bash
cp backend/.env.example backend/.env
```
3. (Opcional) Edite `backend/.env` com suas credenciais OAuth (GitHub/Google), `OPENAI_API_KEY` e credenciais MinIO/RabbitMQ.
4. Suba a stack:
```bash
cd backend
docker compose up -d
```
5. Verifique saúde:
```bash
curl http://localhost:8000/healthz
```
6. Acesse:
- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs

Credenciais padrão:
| Serviço | URL | Usuário | Senha |
|---|---|---|---|
| Admin do sistema (frontend) | http://localhost:3000 | admin@promptuario.health | Admin@12345 |
| Grafana | http://localhost:3001 | admin | admin |
| RabbitMQ Management | http://localhost:15672 | promptuario | promptuario_pass |
| MinIO Console | http://localhost:9001 | promptuario | promptuario_pass |

Variáveis de ambiente (explicação selecionada):
- `DATABASE_URL` — string de conexão PostgreSQL (obrigatória para cada serviço; ex.: `postgresql://user:pass@db:5432/iam_db`)
- `REDIS_URL` — URL do Redis (ex.: `redis://redis:6379/0`)
- `RABBITMQ_URL` — URL de conexão (ex.: `amqp://promptuario:promptuario_pass@rabbitmq:5672/`)
- `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` — MinIO para arquivos/backups
- `OPENAI_API_KEY` — (opcional) chave para integrações LLM
- `OAUTH_GITHUB_CLIENT_ID`, `OAUTH_GITHUB_CLIENT_SECRET` — (opcional) credenciais OAuth
- `BACKUP_SCHEDULE_HOURS` — frequência de backup (padrão 24)
- `BACKUP_RETENTION_DAYS` — retenção (padrão 7)

Comandos Make (disponíveis no `backend/Makefile`):
- `make up` — sobe todos os serviços (docker compose up -d)
- `make down` — para e remove containers
- `make logs` — tail dos logs agrupados
- `make health` — checa /healthz dos serviços
- `make tests` — executa suíte de testes definida
