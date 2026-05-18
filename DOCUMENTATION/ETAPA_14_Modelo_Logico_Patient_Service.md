# ETAPA 14.2 — PATIENT SERVICE

Este documento descreve o modelo lógico do Patient Service, responsável pelo cadastro clínico-demográfico do paciente e seus históricos básicos.

## Tabelas

### patients

| Campo | Tipo | Nulo | Chave | Descrição |
|------|------|------|------|-----------|
| id | UUID/String(36) | Não | PK | Identificador do paciente |
| user_id | UUID/String(36) | Não | UK | Referência lógica ao usuário IAM |
| full_name | varchar(255) | Não | - | Nome completo |
| cpf | varchar(14) | Sim | UK | CPF, quando informado |
| date_of_birth | date | Sim | - | Data de nascimento |
| gender | enum | Sim | - | M, F, OTHER |
| blood_type | varchar(5) | Sim | - | Tipo sanguíneo |
| phone | varchar(20) | Sim | - | Telefone |
| email | varchar(255) | Sim | - | E-mail de contato |
| street | varchar(255) | Sim | - | Endereço |
| city | varchar(100) | Sim | - | Cidade |
| state | varchar(2) | Sim | - | UF |
| zip_code | varchar(9) | Sim | - | CEP |
| emergency_name | varchar(255) | Sim | - | Contato de emergência |
| emergency_phone | varchar(20) | Sim | - | Telefone de emergência |
| emergency_relation | varchar(50) | Sim | - | Parentesco |
| notes | text | Sim | - | Observações |
| is_active | boolean | Não | - | Ativo/inativo |
| anonymized | boolean | Não | - | Anonimizado |
| created_at | datetime tz | Não | - | Criação |
| updated_at | datetime tz | Não | - | Atualização |

### allergies

| Campo | Tipo | Nulo | Chave | Descrição |
|------|------|------|------|-----------|
| id | UUID/String(36) | Não | PK | Identificador da alergia |
| patient_id | UUID/String(36) | Não | FK -> patients.id | Paciente dono |
| substance | varchar(255) | Não | - | Substância/alérgeno |
| severity | enum | Não | - | MILD, MODERATE, SEVERE |
| reaction_type | varchar(255) | Sim | - | Tipo de reação |
| notes | text | Sim | - | Observações |
| created_at | datetime tz | Não | - | Criação |

### vaccines

| Campo | Tipo | Nulo | Chave | Descrição |
|------|------|------|------|-----------|
| id | UUID/String(36) | Não | PK | Identificador da vacina |
| patient_id | UUID/String(36) | Não | FK -> patients.id | Paciente dono |
| name | varchar(255) | Não | - | Nome da vacina |
| dose | varchar(50) | Sim | - | Dose |
| applied_at | date | Sim | - | Data de aplicação |
| next_dose_at | date | Sim | - | Próxima dose |
| notes | text | Sim | - | Observações |
| created_at | datetime tz | Não | - | Criação |

### continuous_medications

| Campo | Tipo | Nulo | Chave | Descrição |
|------|------|------|------|-----------|
| id | UUID/String(36) | Não | PK | Identificador da medicação |
| patient_id | UUID/String(36) | Não | FK -> patients.id | Paciente dono |
| name | varchar(255) | Não | - | Nome do medicamento |
| dosage | varchar(100) | Não | - | Dose |
| frequency | varchar(100) | Não | - | Frequência |
| prescribing_doctor | varchar(255) | Sim | - | Médico prescritor |
| started_at | date | Sim | - | Início |
| notes | text | Sim | - | Observações |
| active | boolean | Não | - | Em uso |
| created_at | datetime tz | Não | - | Criação |

## Relacionamentos

- `patients 1 -> N allergies`
- `patients 1 -> N vaccines`
- `patients 1 -> N continuous_medications`
- `patients.user_id` referencia logicamente `users.id` do IAM Service.