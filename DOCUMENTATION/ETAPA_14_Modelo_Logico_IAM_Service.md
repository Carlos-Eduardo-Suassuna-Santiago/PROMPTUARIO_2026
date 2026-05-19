# ETAPA 14.1 — IAM SERVICE

Este documento descreve o modelo lógico do IAM Service, responsável por identidade, autenticação e ciclo de vida de acesso.

## Tabelas

### users

| Campo | Tipo | Nulo | Chave | Descrição |
|------|------|------|------|-----------|
| id | UUID/String(36) | Não | PK | Identificador do usuário |
| email | varchar(255) | Não | UK | E-mail único de acesso |
| hashed_password | varchar(128) | Não | - | Senha com hash |
| full_name | varchar(255) | Não | - | Nome completo |
| role | enum | Não | - | ADMIN, DOCTOR, ATTENDANT, PATIENT |
| is_active | boolean | Não | - | Indica se está ativo |
| created_at | datetime tz | Não | - | Criação |
| updated_at | datetime tz | Não | - | Atualização |
| deactivated_at | datetime tz | Sim | - | Desativação |
| deactivation_reason | varchar(255) | Sim | - | Motivo da desativação |

### refresh_tokens

| Campo | Tipo | Nulo | Chave | Descrição |
|------|------|------|------|-----------|
| id | UUID/String(36) | Não | PK | Identificador do token |
| user_id | UUID/String(36) | Não | FK -> users.id | Usuário dono do token |
| token_hash | varchar(128) | Não | UK | Hash do refresh token |
| expires_at | datetime tz | Não | - | Expiração |
| revoked | boolean | Não | - | Revogação |
| created_at | datetime tz | Não | - | Criação |

## Relacionamento

- `users 1 -> N refresh_tokens`
- Um usuário pode possuir múltiplos refresh tokens válidos ou revogados ao longo do tempo.