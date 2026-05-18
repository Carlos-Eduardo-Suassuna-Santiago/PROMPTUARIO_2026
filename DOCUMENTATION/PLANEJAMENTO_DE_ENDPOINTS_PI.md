# Planejamento de Endpoints do PI do Sistema

Documento centralizado de referência para os endpoints do PROMPTUARIO Backend, cobrindo Gateway, microserviços, rotas públicas, rotas autenticadas e o status geral de cada superfície exposta.

---

## 1. Visão Geral

### 1.1 Base de acesso
- **Gateway:** `http://localhost:8000`
- **Base API via Gateway:** `http://localhost:8000/api/v1`
- **Serviços diretos:** `:8001` a `:8005`

### 1.2 Responsabilidades do Gateway
- Autenticação JWT centralizada
- Validação de headers `Authorization: Bearer <token>`
- Rate limiting para rotas autenticadas e anônimas
- Roteamento para os serviços downstream
- Health check agregado dos serviços

---

## 2. Roteamento do Gateway (:8000)

| Prefixo | Destino | Auth | Observação |
|---|---|---:|---|
| `/healthz` | Gateway | Não | Health check do próprio gateway |
| `/healthz/services` | Gateway | Não | Agrega health dos 5 serviços |
| `/api/v1/auth/login` | IAM | Não | Login inicial |
| `/api/v1/auth/refresh` | IAM | Não | Renovação de refresh token |
| `/api/v1/auth/*` | IAM | Sim | Demais rotas de autenticação |
| `/api/v1/users/*` | IAM | Sim | Gestão de usuários |
| `/api/v1/patients/*` | Patient | Sim | Cadastro e dados clínicos do paciente |
| `/api/v1/appointments/*` | Clinical | Sim | Agenda e consultas |
| `/api/v1/records/*` | Clinical | Sim | Prontuários, prescrições e exames |
| `/api/v1/schedules/*` | Clinical | Sim | Agenda médica e slots |
| `/api/v1/ai/*` | AI | Sim | Análises assíncronas |
| `/api/v1/reports/*` | Reporting | Sim | Relatórios e exports |

---

## 3. IAM Service (:8001)

Serviço de autenticação, autorização e gerenciamento de usuários.

### 3.1 Health e Informações

| Método | Endpoint | Descrição | Status |
|---|---|---|---|
| GET | `/healthz` | Health check | Implementado |
| GET | `/docs` | Swagger UI | Implementado |

### 3.2 Autenticação

| Método | Endpoint | Descrição | Role | Status |
|---|---|---|---|---|
| POST | `/api/v1/auth/login` | Autenticar usuário | Público | Implementado |
| POST | `/api/v1/auth/refresh` | Renovar access token | Público | Implementado |
| POST | `/api/v1/auth/logout` | Revogar refresh token e blacklist do access token | Autenticado | Implementado |
| POST | `/api/v1/auth/change-password` | Alterar senha do usuário logado | Autenticado | Implementado |

### 3.3 Usuários

| Método | Endpoint | Descrição | Role | Status |
|---|---|---|---|---|
| GET | `/api/v1/users` | Listar usuários | ADMIN | Implementado |
| GET | `/api/v1/users/me` | Obter dados do usuário logado | Autenticado | Implementado |
| GET | `/api/v1/users/{id}` | Obter usuário por ID | ADMIN | Implementado |
| POST | `/api/v1/users` | Criar usuário | ADMIN | Implementado |
| PUT | `/api/v1/users/{id}` | Atualizar usuário | ADMIN, SELF | Implementado |
| PUT | `/api/v1/users/{id}/role` | Atribuir role | ADMIN | Implementado |
| DELETE | `/api/v1/users/{id}` | Desativar usuário | ADMIN | Implementado |

### 3.4 Observações de contrato
- O seed do primeiro administrador usa `admin@promptuario.health` e `Admin@12345`.
- As respostas de login retornam `access_token`, `refresh_token`, `token_type` e `expires_in`.

---

## 4. Patient Service (:8002)

Serviço de cadastro e manutenção dos dados do paciente.

### 4.1 Health e Informações

| Método | Endpoint | Descrição | Status |
|---|---|---|---|
| GET | `/healthz` | Health check | Implementado |
| GET | `/docs` | Swagger UI | Implementado |

### 4.2 Pacientes

| Método | Endpoint | Descrição | Role | Status |
|---|---|---|---|---|
| POST | `/api/v1/patients` | Criar paciente | DOCTOR, ATTENDANT, ADMIN | Implementado |
| GET | `/api/v1/patients` | Listar pacientes | DOCTOR, ATTENDANT, ADMIN | Implementado |
| GET | `/api/v1/patients/me` | Obter cadastro do paciente logado | PATIENT | Implementado |
| GET | `/api/v1/patients/{id}` | Obter paciente por ID | PATIENT(own), DOCTOR, ADMIN | Implementado |
| PATCH | `/api/v1/patients/{id}` | Atualizar paciente | PATIENT(own), DOCTOR, ADMIN | Implementado |
| DELETE | `/api/v1/patients/{id}` | Anonimizar paciente | ADMIN | Implementado |

### 4.3 Alergias

| Método | Endpoint | Descrição | Role | Status |
|---|---|---|---|---|
| POST | `/api/v1/patients/{id}/allergies` | Adicionar alergia | PATIENT(own), DOCTOR, ADMIN | Implementado |
| GET | `/api/v1/patients/{id}/allergies` | Listar alergias | PATIENT(own), DOCTOR, ADMIN | Implementado |
| DELETE | `/api/v1/patients/{id}/allergies/{allergyId}` | Remover alergia | PATIENT(own), DOCTOR, ADMIN | Planejado |

### 4.4 Medicações Contínuas

| Método | Endpoint | Descrição | Role | Status |
|---|---|---|---|---|
| POST | `/api/v1/patients/{id}/medications` | Adicionar medicação | PATIENT(own), DOCTOR, ADMIN | Implementado |
| GET | `/api/v1/patients/{id}/medications` | Listar medicações | PATIENT(own), DOCTOR, ADMIN | Implementado |
| PATCH | `/api/v1/patients/{id}/medications/{medId}` | Atualizar medicação | PATIENT(own), DOCTOR, ADMIN | Planejado |
| DELETE | `/api/v1/patients/{id}/medications/{medId}` | Remover medicação | PATIENT(own), DOCTOR, ADMIN | Planejado |

### 4.5 Vacinação

| Método | Endpoint | Descrição | Role | Status |
|---|---|---|---|---|
| POST | `/api/v1/patients/{id}/vaccines` | Registrar vacina | DOCTOR, ATTENDANT, ADMIN | Implementado |
| GET | `/api/v1/patients/{id}/vaccines` | Listar vacinas | PATIENT(own), DOCTOR, ADMIN | Implementado |
| DELETE | `/api/v1/patients/{id}/vaccines/{vaccineId}` | Remover vacina | ADMIN | Planejado |

---

## 5. Clinical Service (:8003)

Serviço de consultas, prontuários, prescrições e agenda clínica.

### 5.1 Health e Informações

| Método | Endpoint | Descrição | Status |
|---|---|---|---|
| GET | `/healthz` | Health check | Implementado |
| GET | `/docs` | Swagger UI | Implementado |

### 5.2 Agendamentos

| Método | Endpoint | Descrição | Role | Status |
|---|---|---|---|---|
| POST | `/api/v1/appointments` | Criar agendamento | PATIENT, ATTENDANT, ADMIN | Implementado |
| GET | `/api/v1/appointments` | Listar agendamentos | DOCTOR, ATTENDANT, ADMIN | Implementado |
| GET | `/api/v1/appointments/{id}` | Obter agendamento | PATIENT(own), DOCTOR, ADMIN | Implementado |
| PATCH | `/api/v1/appointments/{id}` | Atualizar agendamento | ATTENDANT, ADMIN | Planejado |
| PATCH | `/api/v1/appointments/{id}/cancel` | Cancelar agendamento | PATIENT(24h), DOCTOR, ATTENDANT, ADMIN | Implementado |
| PATCH | `/api/v1/appointments/{id}/complete` | Marcar como concluído | DOCTOR, ADMIN | Implementado |

### 5.3 Prontuários

| Método | Endpoint | Descrição | Role | Status |
|---|---|---|---|---|
| POST | `/api/v1/records` | Criar prontuário | DOCTOR, ADMIN | Implementado |
| GET | `/api/v1/records` | Listar prontuários | DOCTOR, ADMIN | Planejado |
| GET | `/api/v1/records/{id}` | Obter prontuário | PATIENT(own), DOCTOR, ADMIN | Implementado |
| PATCH | `/api/v1/records/{id}` | Atualizar prontuário | DOCTOR(owner), ADMIN | Implementado |
| GET | `/api/v1/records/{id}/history` | Histórico de auditoria | DOCTOR, ADMIN | Planejado |
| GET | `/api/v1/records/patient/{patientId}` | Prontuários de um paciente | DOCTOR, ADMIN | Implementado |

### 5.4 Prescrições

| Método | Endpoint | Descrição | Role | Status |
|---|---|---|---|---|
| POST | `/api/v1/records/{recordId}/prescriptions` | Gerar prescrição | DOCTOR | Implementado |
| GET | `/api/v1/records/{recordId}/prescriptions` | Listar prescrições do prontuário | PATIENT(own), DOCTOR, ADMIN | Planejado |
| GET | `/api/v1/prescriptions/{id}` | Obter prescrição | PATIENT(own), DOCTOR, ADMIN | Planejado |
| PATCH | `/api/v1/prescriptions/{id}` | Atualizar prescrição | DOCTOR, ADMIN | Planejado |

### 5.5 Exames

| Método | Endpoint | Descrição | Role | Status |
|---|---|---|---|---|
| POST | `/api/v1/records/{recordId}/exams` | Solicitar exame | DOCTOR | Implementado |
| PUT | `/api/v1/records/{recordId}/exams/{examId}/result` | Registrar resultado do exame | DOCTOR, ADMIN | Implementado |

### 5.6 Agenda Médica

| Método | Endpoint | Descrição | Role | Status |
|---|---|---|---|---|
| POST | `/api/v1/schedules` | Criar agenda | DOCTOR, ADMIN | Planejado |
| GET | `/api/v1/schedules` | Listar agendas | DOCTOR, ATTENDANT, ADMIN | Planejado |
| GET | `/api/v1/schedules/{id}/available-slots` | Listar slots disponíveis | Público | Planejado |
| PATCH | `/api/v1/schedules/{id}` | Atualizar agenda | DOCTOR(owner), ADMIN | Planejado |
| DELETE | `/api/v1/schedules/{id}` | Deletar agenda | DOCTOR(owner), ADMIN | Planejado |

---

## 6. AI Service (:8004)

Serviço de análise assistida por IA, com execução assíncrona.

### 6.1 Health e Informações

| Método | Endpoint | Descrição | Status |
|---|---|---|---|
| GET | `/healthz` | Health check | Implementado |
| GET | `/docs` | Swagger UI | Implementado |

### 6.2 Análises

| Método | Endpoint | Descrição | Role | Status |
|---|---|---|---|---|
| POST | `/api/v1/ai/analyze` | Solicitar análise assíncrona | DOCTOR, ADMIN | Implementado |
| GET | `/api/v1/ai/jobs/{jobId}` | Consultar status da análise | DOCTOR, ADMIN | Implementado |
| GET | `/api/v1/ai/records/{recordId}/analyses` | Listar análises do prontuário | DOCTOR, ADMIN | Implementado |
| DELETE | `/api/v1/ai/jobs/{jobId}` | Cancelar análise | DOCTOR, ADMIN | Planejado |

### 6.3 Tipos de análise
- `DRUG_INTERACTION_CHECK`
- `SYMPTOM_ANALYSIS`
- `CLINICAL_SUMMARY`
- `DIAGNOSTIC_SUGGESTION`

---

## 7. Reporting Service (:8005)

Serviço de relatórios e métricas operacionais.

### 7.1 Health e Informações

| Método | Endpoint | Descrição | Status |
|---|---|---|---|
| GET | `/healthz` | Health check | Implementado |
| GET | `/docs` | Swagger UI | Implementado |

### 7.2 Relatórios

| Método | Endpoint | Descrição | Role | Status |
|---|---|---|---|---|
| POST | `/api/v1/reports/export` | Solicitar exportação assíncrona | DOCTOR, ADMIN | Implementado |
| GET | `/api/v1/reports/export/{jobId}` | Consultar status do relatório | DOCTOR, ADMIN | Implementado |
| GET | `/api/v1/reports/export/{jobId}/download` | Download do relatório | DOCTOR, ADMIN | Implementado |
| GET | `/api/v1/reports/summary` | Resumo operacional | ADMIN | Implementado |
| GET | `/api/v1/reports/consultations` | Consultas por período | DOCTOR, ADMIN | Implementado |
| GET | `/api/v1/reports/patients` | Novos pacientes por período | ADMIN | Implementado |
| GET | `/api/v1/reports/doctors` | Consultas por médico | ADMIN | Implementado |

### 7.3 Tipos de relatório
- `CONSULTATIONS`
- `PATIENTS`
- `DOCTORS`
- `PRESCRIPTIONS`

### 7.4 Formatos de saída
- `JSON`
- `CSV`
- `PDF`

---

## 8. Convenções Globais

### 8.1 Autenticação
- Header obrigatório: `Authorization: Bearer <JWT_TOKEN>`
- Endpoints públicos: `healthz`, `docs`, `auth/login`, `auth/refresh`
- Demais rotas exigem autenticação

### 8.2 Respostas padrão
- `200 OK` para leitura/atualização bem-sucedida
- `201 Created` para criação
- `202 Accepted` para jobs assíncronos
- `204 No Content` para ações sem corpo de resposta
- `401 Unauthorized` para autenticação inválida ou ausente
- `403 Forbidden` para permissão insuficiente
- `404 Not Found` para recurso inexistente
- `409 Conflict` para duplicidade ou conflito de regra

### 8.3 Paginação
- Parâmetros comuns: `page`, `size`
- Ordenação padrão: `created_at DESC` ou `updated_at DESC` conforme a entidade

### 8.4 Regras transversais
- Toda operação sensível deve registrar auditoria
- Eventos de domínio são publicados via RabbitMQ quando aplicável
- Processos pesados e exportações devem usar execução assíncrona

---

## 9. Resumo de Cobertura

| Serviço | Endpoints listados | Implementados | Planejados |
|---|---:|---:|---:|
| Gateway | 2 + roteamento | 2 | 0 |
| IAM | 11 | 11 | 0 |
| Patient | 14 | 11 | 3 |
| Clinical | 21 | 13 | 8 |
| AI | 4 | 3 | 1 |
| Reporting | 7 | 7 | 0 |

---

## 10. Observação Final

Este documento serve como referência de planejamento de endpoints do PI do sistema e pode ser usado como base para validação de escopo, API design, testes manuais e automação de smoke tests.
