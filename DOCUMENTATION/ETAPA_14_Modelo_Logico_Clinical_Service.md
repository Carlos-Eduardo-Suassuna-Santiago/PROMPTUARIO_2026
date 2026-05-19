# ETAPA 14.3 — CLINICAL SERVICE

Este documento descreve o modelo lógico do Clinical Service, que concentra a agenda médica, os atendimentos e os artefatos assistenciais.

## Tabelas

### patient_projections

| Campo | Tipo | Nulo | Chave | Descrição |
|------|------|------|------|-----------|
| id | UUID/String(36) | Não | PK | ID do paciente projetado |
| user_id | UUID/String(36) | Não | Índice | ID lógico do usuário |
| full_name | varchar(255) | Não | - | Nome do paciente |
| phone | varchar(20) | Sim | - | Telefone |
| date_of_birth | date | Sim | - | Nascimento |
| blood_type | varchar(5) | Sim | - | Tipo sanguíneo |
| updated_at | datetime tz | Não | - | Atualização |

### doctor_schedules

| Campo | Tipo | Nulo | Chave | Descrição |
|------|------|------|------|-----------|
| id | UUID/String(36) | Não | PK | Identificador da agenda |
| doctor_id | UUID/String(36) | Não | Índice | Médico responsável |
| specialty | varchar(100) | Sim | - | Especialidade |
| is_active | boolean | Não | - | Agenda ativa |
| created_at | datetime tz | Não | - | Criação |

### time_slots

| Campo | Tipo | Nulo | Chave | Descrição |
|------|------|------|------|-----------|
| id | UUID/String(36) | Não | PK | Identificador do slot |
| schedule_id | UUID/String(36) | Não | FK -> doctor_schedules.id | Agenda dona |
| slot_date | date | Não | - | Data |
| start_time | varchar(5) | Não | - | Início HH:MM |
| end_time | varchar(5) | Não | - | Fim HH:MM |
| is_available | boolean | Não | - | Disponível |
| created_at | datetime tz | Não | - | Criação |

### appointments

| Campo | Tipo | Nulo | Chave | Descrição |
|------|------|------|------|-----------|
| id | UUID/String(36) | Não | PK | Identificador do agendamento |
| patient_id | UUID/String(36) | Não | Índice | Paciente |
| doctor_id | UUID/String(36) | Não | Índice | Médico |
| slot_id | UUID/String(36) | Sim | FK -> time_slots.id | Slot reservado |
| scheduled_at | datetime tz | Não | - | Data/hora agendada |
| appointment_type | enum | Não | - | CONSULTATION, RETURN, EXAM, URGENT |
| specialty | varchar(100) | Sim | - | Especialidade |
| status | enum | Não | - | SCHEDULED, CONFIRMED, COMPLETED, CANCELLED, NO_SHOW |
| cancellation_reason | varchar(255) | Sim | - | Motivo |
| cancelled_by | UUID/String(36) | Sim | - | Cancelado por |
| cancelled_at | datetime tz | Sim | - | Quando cancelado |
| notes | text | Sim | - | Observações |
| created_by | UUID/String(36) | Não | - | Autor da criação |
| created_at | datetime tz | Não | - | Criação |
| updated_at | datetime tz | Não | - | Atualização |

### medical_records

| Campo | Tipo | Nulo | Chave | Descrição |
|------|------|------|------|-----------|
| id | UUID/String(36) | Não | PK | Identificador do prontuário |
| appointment_id | UUID/String(36) | Não | UK, FK -> appointments.id | Um prontuário por consulta |
| patient_id | UUID/String(36) | Não | Índice | Paciente |
| doctor_id | UUID/String(36) | Não | Índice | Médico |
| chief_complaint | text | Não | - | Queixa principal |
| anamnesis | text | Sim | - | Anamnese |
| physical_exam | text | Sim | - | Exame físico |
| diagnosis | text | Sim | - | Diagnóstico |
| diagnosis_codes | JSON | Não | - | Lista de códigos |
| treatment_plan | text | Sim | - | Plano terapêutico |
| observations | text | Sim | - | Observações |
| ai_analysis_id | UUID/String(36) | Sim | - | ID lógico da análise IA |
| created_at | datetime tz | Não | - | Criação |
| updated_at | datetime tz | Não | - | Atualização |

### medical_record_history

| Campo | Tipo | Nulo | Chave | Descrição |
|------|------|------|------|-----------|
| id | UUID/String(36) | Não | PK | Identificador do evento histórico |
| record_id | UUID/String(36) | Não | FK -> medical_records.id | Prontuário origem |
| changed_by | UUID/String(36) | Não | - | Usuário que alterou |
| change_type | varchar(50) | Não | - | Tipo de alteração |
| snapshot | JSON | Não | - | Cópia do estado |
| created_at | datetime tz | Não | - | Data da alteração |

### prescriptions

| Campo | Tipo | Nulo | Chave | Descrição |
|------|------|------|------|-----------|
| id | UUID/String(36) | Não | PK | Identificador da prescrição |
| record_id | UUID/String(36) | Não | FK -> medical_records.id | Prontuário origem |
| patient_id | UUID/String(36) | Não | - | Paciente |
| doctor_id | UUID/String(36) | Não | - | Médico |
| medications | JSON | Não | - | Lista de medicamentos |
| instructions | text | Sim | - | Orientações |
| valid_days | integer | Não | - | Dias de validade |
| pdf_s3_key | varchar(500) | Sim | - | Arquivo no MinIO |
| created_at | datetime tz | Não | - | Criação |

### exam_requests

| Campo | Tipo | Nulo | Chave | Descrição |
|------|------|------|------|-----------|
| id | UUID/String(36) | Não | PK | Identificador da solicitação |
| record_id | UUID/String(36) | Não | FK -> medical_records.id | Prontuário origem |
| patient_id | UUID/String(36) | Não | - | Paciente |
| doctor_id | UUID/String(36) | Não | - | Médico |
| exam_type | varchar(255) | Não | - | Tipo de exame |
| urgency | enum | Não | - | ROUTINE, URGENT, EMERGENCY |
| instructions | text | Sim | - | Instruções |
| result | text | Sim | - | Resultado |
| result_date | datetime tz | Sim | - | Data do resultado |
| created_at | datetime tz | Não | - | Criação |

## Relacionamentos

- `doctor_schedules 1 -> N time_slots`
- `time_slots 1 -> N appointments` via slot selecionado em `appointments.slot_id`
- `appointments 1 -> 0..1 medical_records`
- `medical_records 1 -> N prescriptions`
- `medical_records 1 -> N exam_requests`
- `medical_records 1 -> N medical_record_history`
- `patient_projections` é uma projeção local mantida por eventos do Patient Service.