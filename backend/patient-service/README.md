# PROMPTUARIO — Patient Service

O Patient Service é o módulo responsável por guardar as informações principais dos pacientes. Ele funciona como o cadastro central do prontuário eletrônico.

## Contexto no ecossistema Promptuário

```
Gateway (:8000) → Patient Service (:8002) → PostgreSQL / RabbitMQ
```

O Patient Service está posicionado atrás do **API Gateway** e se comunica com:
- **PostgreSQL** — persistência de dados de pacientes, alergias, vacinas e medicamentos contínuos
- **RabbitMQ** — publicação de eventos de domínio (`PatientCreated`, `PatientUpdated`, `AllergyAdded`)

Porta padrão do serviço: `8002`

## Para que serve

Este microsserviço existe para manter os dados do paciente organizados e acessíveis. Ele reúne informações básicas, alergias, vacinas e medicamentos contínuos.

## Como funciona, passo a passo

1. Um paciente é cadastrado no sistema.
2. As informações são salvas no banco de dados (PostgreSQL).
3. O usuário pode consultar ou complementar esses dados.
4. Quando houver alterações importantes, o serviço publica eventos para outros módulos (Clinical, AI, Reporting).
5. Esses dados passam a ser usados por outros serviços, como clínico, IA e relatórios.
6. O Patient Service também consome eventos do IAM Service (`UserCreated`, `UserDeactivated`) para manter projeções atualizadas.

## O que ele faz na prática

- cadastra pacientes;
- armazena dados pessoais e clínicos básicos;
- registra alergias;
- registra vacinas;
- acompanha medicamentos contínuos;
- disponibiliza os dados para o restante do sistema;
- publica eventos para integração com outros microsserviços.

## Stack técnica

| Camada        | Tecnologia                        |
|---------------|-----------------------------------|
| API           | FastAPI 0.115+ (Python assíncrono)|
| BD Relacional | PostgreSQL 15 (SQLAlchemy 2 async)|
| Mensageria    | RabbitMQ 3.13 (aio-pika)          |
| Validação     | Pydantic v2                       |

## Conformidade LGPD

- PII (dados pessoais) armazenada exclusivamente no Patient Service
- Outros serviços armazenam apenas `patient_id` (anonimizado)
- Endpoint de anonimização disponível (`DELETE /api/v1/patients/{id}`)
- Histórico imutável de alterações via `MedicalRecordHistory` no Clinical Service

## Pré-requisitos

- PostgreSQL disponível
- RabbitMQ disponível
- Python 3.11+

## Início rápido

### Desenvolvimento local (sem Docker)

```bash
cd backend/patient-service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8002
```

### Com Docker Compose (infraestrutura completa)

```bash
cd backend
docker-compose up --build patient-service
```

## Endpoints principais

| Método | Endpoint                              | Descrição                     |
|--------|---------------------------------------|-------------------------------|
| POST   | `/api/v1/patients`                    | Cadastra um paciente          |
| GET    | `/api/v1/patients`                    | Lista pacientes               |
| GET    | `/api/v1/patients/{id}`               | Consulta um paciente específico|
| POST   | `/api/v1/patients/{id}/allergies`     | Adiciona uma alergia          |
| DELETE | `/api/v1/patients/{id}`               | Anonimiza paciente (LGPD)     |
| GET    | `/healthz`                            | Health check do serviço       |

## Eventos de domínio

| Evento             | Publica/Consome | Exchange               | Descrição                     |
|--------------------|----------------|------------------------|-------------------------------|
| `PatientCreated`   | Publica        | `promptuario.patient`  | Paciente cadastrado           |
| `PatientUpdated`   | Publica        | `promptuario.patient`  | Dados do paciente atualizados |
| `AllergyAdded`     | Publica        | `promptuario.patient`  | Alergia registrada            |
| `UserCreated`      | Consome        | `promptuario.iam`      | Usuário criado (projeção)     |
| `UserDeactivated`  | Consome        | `promptuario.iam`      | Usuário desativado            |

## Exemplo de uso

```bash
curl -X POST http://localhost:8000/api/v1/patients \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "usr_123",
    "full_name": "Maria da Silva",
    "cpf": "123.456.789-00",
    "date_of_birth": "1985-03-22",
    "blood_type": "O+",
    "phone": "+55 84 99999-0000"
  }'
```

> **Nota:** O endpoint é acessado via **Gateway** (`:8000`), que faz o roteamento para o Patient Service (`:8002`).

## Variáveis de ambiente importantes

| Variável          | Descrição                          | Default       |
|-------------------|------------------------------------|---------------|
| `DATABASE_URL`    | URL de conexão com PostgreSQL      | —             |
| `RABBITMQ_URL`    | URL de conexão com RabbitMQ        | —             |
| `JWT_SECRET_KEY`  | Chave secreta JWT (≥32 caracteres) | *obrigatório* |
| `JWT_ALGORITHM`   | Algoritmo JWT                      | `HS256`       |

## Como validar o funcionamento

- acesse `http://localhost:8002/healthz`;
- cadastre um paciente;
- verifique se os dados ficaram salvos corretamente;
- confirme se o evento `PatientCreated` foi publicado (logs do RabbitMQ).

## Testes

```bash
cd backend/patient-service
pytest -q
```

## Documentação relacionada

- [Documentação técnica da etapa 4 (Patient Service)](../../DOCUMENTATION/ETAPA_4_Patient_Service_Fastapi_Clean_Architecture.md)
- [Modelo lógico do banco de dados](../../DOCUMENTATION/ETAPA_14_Modelo_Logico_Patient_Service.md)
- [Arquitetura global do sistema](../../DOCUMENTATION/ETAPA_1_ARQUITETURA_GLOBAL.md)

## Observação final

Esse serviço é a base do cadastro do paciente dentro da plataforma. Ele garante que o restante do sistema tenha dados consistentes para trabalhar.