# DOCUMENTO DE REQUISITOS — HISTÓRIAS DE USUÁRIOS

## PROMPTUARIO Backend — Histórias de Usuários por Épico

Este documento organiza todos os requisitos funcionais do PROMPTUARIO Backend no formato de histórias de usuários seguindo padrão Agile/BDD.

---

## 1. Organização de Requisitos

**Estrutura:**
- **Épico:** Área de negócio ampla
- **História:** Descrição de funcionalidade do usuário
- **Critérios de Aceite:** Validação de completude
- **Estimativa:** Story points (1-13)
- **Prioridade:** CRÍTICO, ALTO, MÉDIO, BAIXO
- **Status:** ⭕ Não iniciado | 🔵 Em progresso | ✅ Completo

---

## 2. ÉPICO 1: AUTENTICAÇÃO E GESTÃO DE ACESSO

### 2.1 H-AUTH-001: Autenticação via Email e Senha

**Como:** Usuário  
**Quero:** Fazer login com email e senha  
**Para:** Acessar o sistema com credenciais seguras

**Critérios de Aceite:**
- [ ] Endpoint `POST /api/v1/auth/login` aceita email e senha
- [ ] Senha é validada com hash bcrypt
- [ ] Retorna JWT access_token e refresh_token em sucesso
- [ ] Retorna 401 em credenciais inválidas
- [ ] Retorna 403 se usuário estiver inativo
- [ ] Log de auditoria registra tentativa (sucesso/falha)

**Estimativa:** 5 pontos  
**Prioridade:** CRÍTICO  
**Status:** ✅ Completo

---

### 2.2 H-AUTH-002: Renovação de Token JWT

**Como:** Usuário com refresh_token válido  
**Quero:** Renovar meu access_token expirado  
**Para:** Manter a sessão ativa sem fazer login novamente

**Critérios de Aceite:**
- [ ] Endpoint `POST /api/v1/auth/refresh` aceita refresh_token válido
- [ ] Retorna novo access_token com TTL de 1 hora
- [ ] Refresh token expira após 7 dias ou é revogado
- [ ] Retorna 401 se refresh_token inválido/expirado
- [ ] Token revogado não pode ser reutilizado

**Estimativa:** 3 pontos  
**Prioridade:** CRÍTICO  
**Status:** ✅ Completo

---

### 2.3 H-AUTH-003: Logout com Revogação de Token

**Como:** Usuário autenticado  
**Quero:** Fazer logout revogando meu token  
**Para:** Encerrar a sessão e impedir acesso não autorizado

**Critérios de Aceite:**
- [ ] Endpoint `POST /api/v1/auth/logout` revoga refresh_token
- [ ] Token é adicionado à blacklist no Redis
- [ ] Requisições posteriores com token revogado retornam 401
- [ ] Retorna 204 No Content em sucesso
- [ ] Auditoria registra logout

**Estimativa:** 3 pontos  
**Prioridade:** ALTO  
**Status:** 📋 Planejado

---

### 2.4 H-AUTH-004: Controle de Acesso por Role (RBAC)

**Como:** Sistema  
**Quero:** Validar que o usuário possui a role necessária  
**Para:** Garantir autorização em endpoints protegidos

**Critérios de Aceite:**
- [ ] Middleware valida claim de role no JWT
- [ ] Roles suportadas: ADMIN, DOCTOR, ATTENDANT, PATIENT
- [ ] Endpoint rejeitado com 403 se role insuficiente
- [ ] Endpoints podem exigir role específica ou múltiplas
- [ ] Self-access: usuário pode acessar seu próprio recurso

**Estimativa:** 5 pontos  
**Prioridade:** CRÍTICO  
**Status:** ✅ Completo

---

### 2.5 H-AUTH-005: Autenticação em Gateway

**Como:** Cliente do frontend  
**Quero:** Todos os endpoints serem roteados pelo Gateway com validação de JWT  
**Para:** Ter um ponto único de autenticação

**Critérios de Aceite:**
- [ ] Gateway valida JWT em todas as requisições (exceto login/refresh)
- [ ] Token inválido resulta em 401
- [ ] Header `Authorization: Bearer <TOKEN>` obrigatório
- [ ] Rate limiting aplicado: 300 req/min autenticado, 30 req/min anônimo
- [ ] Requisições rejeitadas sem token em endpoints protegidos

**Estimativa:** 8 pontos  
**Prioridade:** CRÍTICO  
**Status:** ✅ Completo

---

## 3. ÉPICO 2: GESTÃO DE USUÁRIOS

### 3.1 H-USER-001: Criar Usuário (Admin)

**Como:** Administrador  
**Quero:** Criar novo usuário no sistema  
**Para:** Adicionar médicos, atendentes ou pacientes

**Critérios de Aceite:**
- [ ] Endpoint `POST /api/v1/users` cria usuário com email único
- [ ] Apenas ADMIN pode criar
- [ ] Campos obrigatórios: email, full_name, password, role
- [ ] Email validado como formato correto
- [ ] Senha com hash bcrypt (mínimo 12 caracteres)
- [ ] Retorna 201 com dados do usuário criado
- [ ] Retorna 409 se email já existe
- [ ] Auditoria registra criação

**Estimativa:** 5 pontos  
**Prioridade:** CRÍTICO  
**Status:** 📋 Planejado

---

### 3.2 H-USER-002: Listar Usuários

**Como:** Administrador  
**Quero:** Listar todos os usuários do sistema com paginação  
**Para:** Gerenciar acesso e permissões

**Critérios de Aceite:**
- [ ] Endpoint `GET /api/v1/users` retorna lista paginada
- [ ] Apenas ADMIN pode acessar
- [ ] Suporta filtro por role, is_active
- [ ] Ordena por created_at DESC
- [ ] Retorna 200 com array de usuários
- [ ] Máximo 100 resultados por página

**Estimativa:** 3 pontos  
**Prioridade:** ALTO  
**Status:** ✅ Completo

---

### 3.3 H-USER-003: Obter Detalhes de Usuário

**Como:** Usuário ou Administrador  
**Quero:** Consultar informações de um usuário específico  
**Para:** Visualizar perfil

**Critérios de Aceite:**
- [ ] Endpoint `GET /api/v1/users/{id}` retorna dados do usuário
- [ ] Usuário pode acessar dados próprios (self)
- [ ] ADMIN pode acessar qualquer usuário
- [ ] Retorna 200 com dados do usuário
- [ ] Retorna 404 se usuário não existe
- [ ] Retorna 403 se sem permissão

**Estimativa:** 2 pontos  
**Prioridade:** MÉDIO  
**Status:** 📋 Planejado

---

### 3.4 H-USER-004: Atualizar Usuário

**Como:** Usuário ou Administrador  
**Quero:** Atualizar dados do usuário  
**Para:** Manter informações atualizadas

**Critérios de Aceite:**
- [ ] Endpoint `PATCH /api/v1/users/{id}` atualiza campos
- [ ] Usuário atualiza dados próprios
- [ ] ADMIN atualiza qualquer usuário
- [ ] Campos atualizáveis: full_name, role (ADMIN only)
- [ ] Email não pode ser alterado após criação
- [ ] Retorna 200 com dados atualizados
- [ ] Auditoria registra mudanças

**Estimativa:** 3 pontos  
**Prioridade:** MÉDIO  
**Status:** 📋 Planejado

---

### 3.5 H-USER-005: Desativar Usuário (LGPD)

**Como:** Administrador  
**Quero:** Desativar um usuário  
**Para:** Revogar acesso sem perder histórico (conformidade)

**Critérios de Aceite:**
- [ ] Endpoint `DELETE /api/v1/users/{id}` desativa usuário
- [ ] Apenas ADMIN pode desativar
- [ ] Marca `is_active = false` e `deactivated_at`
- [ ] Usuário desativo não consegue fazer login
- [ ] Histórico é preservado (não deleta dados)
- [ ] Retorna 204 No Content
- [ ] Auditoria registra desativação e motivo

**Estimativa:** 3 pontos  
**Prioridade:** ALTO  
**Status:** 📋 Planejado

---

## 4. ÉPICO 3: GESTÃO DE PACIENTES

### 4.1 H-PATIENT-001: Cadastro de Paciente

**Como:** Um Atendente  
**Quero:** Cadastrar um novo paciente com suas informações pessoais e de contato  
**Para:** Que o paciente possa ser identificado e tenha seu prontuário criado no sistema

**Critérios de Aceite:**
- [ ] O sistema deve permitir a inserção de nome completo, CPF único, data de nascimento, endereço, telefone e e-mail
- [ ] O CPF deve ser validado no momento do cadastro
- [ ] O sistema deve notificar o atendente em caso de CPF duplicado
- [ ] Após o cadastro, o paciente deve ter um perfil de usuário associado

**Estimativa:** 5 pontos  
**Prioridade:** CRÍTICO  
**Status:** ✅ Completo

---

### 4.2 H-PATIENT-002: Listar Pacientes

**Como:** Médico ou Atendente  
**Quero:** Listar pacientes com busca e filtros  
**Para:** Encontrar o paciente correto

**Critérios de Aceite:**
- [ ] Endpoint `GET /api/v1/patients` retorna lista
- [ ] Requer role DOCTOR, ATTENDANT ou ADMIN
- [ ] Suporta busca por nome, CPF, telefone
- [ ] Paginação: 50 resultados por página
- [ ] Retorna 200 com array de pacientes
- [ ] Ordena por updated_at DESC

**Estimativa:** 3 pontos  
**Prioridade:** ALTO  
**Status:** ✅ Completo

---

### 4.3 H-PATIENT-003: Visualizar Detalhes do Paciente

**Como:** Paciente, Médico ou Administrador  
**Quero:** Ver informações completas do paciente  
**Para:** Consultar histórico e dados pessoais

**Critérios de Aceite:**
- [ ] Endpoint `GET /api/v1/patients/{id}` retorna dados completos
- [ ] Paciente visualiza dados próprios
- [ ] Médico pode visualizar qualquer paciente
- [ ] Retorna 200 com todos os campos do paciente
- [ ] Retorna 404 se paciente não existe
- [ ] Retorna 403 se acesso negado

**Estimativa:** 2 pontos  
**Prioridade:** CRÍTICO  
**Status:** ✅ Completo

---

### 4.4 H-PATIENT-004: Adicionar Alergia

**Como:** Médico, Paciente ou Atendente  
**Quero:** Registrar uma alergia para o paciente  
**Para:** Avisos de segurança em futuras prescrições

**Critérios de Aceite:**
- [ ] Endpoint `POST /api/v1/patients/{id}/allergies` cria alergia
- [ ] Campos: substance, severity (MILD/MODERATE/SEVERE), reaction_type
- [ ] Retorna 201 com alergia criada
- [ ] Retorna 404 se paciente não existe
- [ ] Evento `AllergyAddedEvent` publicado
- [ ] Auditoria registra adição

**Estimativa:** 2 pontos  
**Prioridade:** CRÍTICO  
**Status:** 📋 Planejado

---

### 4.5 H-PATIENT-005: Listar Alergias

**Como:** Médico, Paciente  
**Quero:** Ver todas as alergias registradas  
**Para:** Prescrever com segurança

**Critérios de Aceite:**
- [ ] Endpoint `GET /api/v1/patients/{id}/allergies` retorna lista
- [ ] Paciente visualiza suas alergias
- [ ] Médico visualiza alergias de qualquer paciente
- [ ] Retorna 200 com array de alergias
- [ ] Inclui severity e reaction_type

**Estimativa:** 2 pontos  
**Prioridade:** ALTO  
**Status:** 📋 Planejado

---

### 4.6 H-PATIENT-006: Adicionar Medicação Contínua

**Como:** Médico ou Paciente  
**Quero:** Registrar medicações contínuas do paciente  
**Para:** Manter controle de tratamentos em andamento

**Critérios de Aceite:**
- [ ] Endpoint `POST /api/v1/patients/{id}/medications` cria medicação
- [ ] Campos: name, dosage, frequency, prescribing_doctor, started_at
- [ ] Retorna 201 com medicação criada
- [ ] Medicação marcada como ativa por padrão
- [ ] Auditoria registra criação

**Estimativa:** 2 pontos  
**Prioridade:** ALTO  
**Status:** 📋 Planejado

---

### 4.7 H-PATIENT-007: Adicionar Registro de Vacina

**Como:** Médico ou Atendente  
**Quero:** Registrar vacina aplicada  
**Para:** Manter calendário vacinal atualizado

**Critérios de Aceite:**
- [ ] Endpoint `POST /api/v1/patients/{id}/vaccines` cria vacina
- [ ] Campos: name, dose, applied_at, next_dose_at
- [ ] Retorna 201 com vacina criada
- [ ] Data de aplicação validada (não futura)
- [ ] Auditoria registra adição

**Estimativa:** 2 pontos  
**Prioridade:** MÉDIO  
**Status:** 📋 Planejado

---

### 4.8 H-PATIENT-008: Anonimizar Paciente (LGPD)

**Como:** Administrador  
**Quero:** Anonimizar dados de um paciente  
**Para:** Cumprir direito ao esquecimento (LGPD)

**Critérios de Aceite:**
- [ ] Endpoint `DELETE /api/v1/patients/{id}` anonimiza paciente
- [ ] Apenas ADMIN pode executar
- [ ] Dados pessoais mascarados ou removidos
- [ ] CPF, email, telefone removidos
- [ ] Histórico mantido para auditoria
- [ ] Retorna 204 No Content
- [ ] Evento `PatientAnonymizedEvent` publicado
- [ ] Auditoria registra anonimização

**Estimativa:** 5 pontos  
**Prioridade:** ALTO  
**Status:** 📋 Planejado

---

## 5. ÉPICO 4: AGENDAMENTOS

### 5.1 H-APPOINTMENT-001: Criar Agenda Médica

**Como:** Médico ou Administrador  
**Quero:** Definir meus horários de atendimento  
**Para:** Disponibilizar slots para agendamento

**Critérios de Aceite:**
- [ ] Endpoint `POST /api/v1/schedules` cria agenda
- [ ] Campos: doctor_id, specialty, time_slots (datas, horários)
- [ ] Requer role DOCTOR ou ADMIN
- [ ] Retorna 201 com agenda criada
- [ ] Slots gerados para intervalo de data

**Estimativa:** 5 pontos  
**Prioridade:** CRÍTICO  
**Status:** ✅ Completo

---

### 5.2 H-APPOINTMENT-002: Visualizar Slots Disponíveis

**Como:** Paciente ou Atendente  
**Quero:** Ver horários disponíveis de um médico  
**Para:** Agendar uma consulta

**Critérios de Aceite:**
- [ ] Endpoint `GET /api/v1/schedules/{doctorId}/available-slots` lista slots
- [ ] Público (sem auth necessária)
- [ ] Retorna apenas slots is_available = true
- [ ] Ordena por data e hora
- [ ] Retorna 200 com array de slots

**Estimativa:** 3 pontos  
**Prioridade:** CRÍTICO  
**Status:** 📋 Planejado

---

### 5.3 H-APPOINTMENT-003: Agendamento de Consulta

**Como:** Um Atendente  
**Quero:** Agendar uma consulta para um paciente com um médico específico em um horário disponível  
**Para:** Que o paciente receba atendimento e o médico organize sua agenda

**Critérios de Aceite:**
- [ ] O sistema deve exibir a disponibilidade de horários dos médicos
- [ ] Não deve ser possível agendar duas consultas para o mesmo médico no mesmo horário
- [ ] O paciente e o médico devem receber uma notificação de agendamento
- [ ] O agendamento deve ser registrado no prontuário do paciente

**Estimativa:** 5 pontos  
**Prioridade:** CRÍTICO  
**Status:** ✅ Completo

---

### 5.4 H-APPOINTMENT-004: Cancelar Consulta

**Como:** Paciente, Médico ou Atendente  
**Quero:** Cancelar uma consulta agendada  
**Para:** Liberar o horário para outro paciente

**Critérios de Aceite:**
- [ ] Endpoint `PATCH /api/v1/appointments/{id}/cancel` cancela
- [ ] Paciente pode cancelar até 24h antes (regra configurável)
- [ ] Médico e atendente podem cancelar sempre
- [ ] Status muda para CANCELLED
- [ ] Slot é marcado como available novamente
- [ ] Retorna 200 com agendamento atualizado
- [ ] Evento `AppointmentCancelledEvent` publicado
- [ ] Auditoria registra cancelamento

**Estimativa:** 4 pontos  
**Prioridade:** ALTO  
**Status:** ✅ Completo

---

## 6. ÉPICO 5: PRONTUÁRIOS MÉDICOS

### 6.1 H-RECORD-001: Registro de Prontuário

**Como:** Um Médico  
**Quero:** Registrar as informações da consulta no prontuário do paciente  
**Para:** Que haja um histórico completo e detalhado do atendimento

**Critérios de Aceite:**
- [ ] O médico deve poder editar o prontuário enquanto a consulta estiver em andamento
- [ ] Após o fechamento do prontuário, apenas comentários adicionais devem ser permitidos
- [ ] Todas as alterações no prontuário devem ser auditadas

**Estimativa:** 5 pontos  
**Prioridade:** CRÍTICO  
**Status:** ✅ Completo

---

### 6.2 H-RECORD-002: Atualizar Prontuário

**Como:** Médico  
**Quero:** Editar diagnóstico, tratamento e observações  
**Para:** Corrigir ou completar informações

**Critérios de Aceite:**
- [ ] O médico deve poder editar o prontuário enquanto a consulta estiver em andamento
- [ ] Após o fechamento do prontuário, apenas comentários adicionais devem ser permitidos
- [ ] Todas as alterações no prontuário devem ser auditadas

**Estimativa:** 4 pontos  
**Prioridade:** ALTO  
**Status:** ✅ Completo (parcial)

---

### 6.3 H-RECORD-003: Visualizar Prontuário

**Como:** Paciente, Médico ou Administrador  
**Quero:** Consultar o prontuário completo  
**Para:** Revisar histórico clínico

**Critérios de Aceite:**
- [ ] Endpoint `GET /api/v1/records/{id}` retorna prontuário
- [ ] Paciente visualiza seus prontuários
- [ ] Médico visualiza prontuários de seus pacientes
- [ ] Retorna 200 com todos os dados do prontuário
- [ ] Inclui prescrições, exames relacionados
- [ ] Retorna 404 se prontuário não existe
- [ ] Retorna 403 se acesso negado

**Estimativa:** 3 pontos  
**Prioridade:** CRÍTICO  
**Status:** ✅ Completo

---

### 6.4 H-RECORD-004: Listar Histórico de Alterações

**Como:** Médico, Paciente ou Administrador  
**Quero:** Ver o histórico completo de alterações do prontuário  
**Para:** Auditar mudanças e evolução

**Critérios de Aceite:**
- [ ] Endpoint `GET /api/v1/records/{id}/history` lista alterações
- [ ] Cada alteração contém: changed_by, change_type, snapshot, timestamp
- [ ] Ordenado por created_at DESC
- [ ] Retorna 200 com array de histórico
- [ ] Dados imutáveis (append-only)
- [ ] Acesso controlado por role

**Estimativa:** 3 pontos  
**Prioridade:** ALTO  
**Status:** 📋 Planejado

---

## 7. ÉPICO 6: PRESCRIÇÕES

### 7.1 H-PRESCRIPTION-001: Gerar Prescrição

**Como:** Médico  
**Quero:** Criar prescrição com lista de medicamentos  
**Para:** Fornecer instruções de medicação ao paciente

**Critérios de Aceite:**
- [ ] Endpoint `POST /api/v1/records/{recordId}/prescriptions` cria
- [ ] Requer role DOCTOR
- [ ] Campos: medications (lista), instructions, valid_days
- [ ] Medicamentos incluem: nome, dosagem, frequência, observações
- [ ] PDF gerado e armazenado em MinIO
- [ ] Retorna 201 com prescrição criada
- [ ] Evento `PrescriptionGeneratedEvent` publicado
- [ ] Auditoria registra geração

**Estimativa:** 5 pontos  
**Prioridade:** CRÍTICO  
**Status:** ✅ Completo

---

### 7.2 H-PRESCRIPTION-002: Visualizar Prescrição

**Como:** Paciente, Médico  
**Quero:** Consultar prescrição e baixar PDF  
**Para:** Seguir instruções de medicação

**Critérios de Aceite:**
- [ ] Endpoint `GET /api/v1/prescriptions/{id}` retorna prescrição
- [ ] Paciente visualiza suas prescrições
- [ ] Médico visualiza prescrições emitidas
- [ ] Retorna 200 com prescrição completa
- [ ] Inclui URL para download do PDF
- [ ] Retorna 404 se não existe

**Estimativa:** 2 pontos  
**Prioridade:** ALTO  
**Status:** 📋 Planejado

---

## 8. ÉPICO 7: ANÁLISE COM IA

### 8.1 H-AI-001: Solicitar Análise Clínica

**Como:** Médico  
**Quero:** Solicitar análise assistida por IA de um prontuário  
**Para:** Obter sugestões diagnósticas

**Critérios de Aceite:**
- [ ] Endpoint `POST /api/v1/ai/analyze` cria job
- [ ] Requer role DOCTOR ou ADMIN
- [ ] Tipos: DRUG_INTERACTION_CHECK, SYMPTOM_ANALYSIS, CLINICAL_SUMMARY
- [ ] Job executado de forma assíncrona
- [ ] Retorna 202 Accepted com job_id
- [ ] Contexto incluído: medicações, alergias, diagnósticos

**Estimativa:** 5 pontos  
**Prioridade:** MÉDIO  
**Status:** ✅ Completo

---

### 8.2 H-AI-002: Consultar Status da Análise

**Como:** Médico  
**Quero:** Verificar o status de um job de análise  
**Para:** Saber quando está pronto

**Critérios de Aceite:**
- [ ] Endpoint `GET /api/v1/ai/jobs/{jobId}` retorna status
- [ ] Status: PENDING, RUNNING, COMPLETED, FAILED
- [ ] Retorna 200 com status e resultado (se completo)
- [ ] Resultado inclui risk_level e análises
- [ ] Retorna 404 se job não existe

**Estimativa:** 2 pontos  
**Prioridade:** MÉDIO  
**Status:** ✅ Completo

---

### 8.3 H-AI-003: Listar Análises de um Prontuário

**Como:** Médico, Paciente  
**Quero:** Ver todas as análises geradas para um prontuário  
**Para:** Revisar histórico de análises

**Critérios de Aceite:**
- [ ] Endpoint `GET /api/v1/ai/records/{recordId}/analyses` lista
- [ ] Retorna 200 com array de jobs/análises
- [ ] Ordena por created_at DESC
- [ ] Inclui status e risk_level de cada uma

**Estimativa:** 2 pontos  
**Prioridade:** MÉDIO  
**Status:** ✅ Completo

---

## 9. ÉPICO 8: RELATÓRIOS

### 9.1 H-REPORT-001: Solicitar Relatório Assíncrono

**Como:** Médico ou Administrador  
**Quero:** Gerar um relatório (consultações, pacientes, prescrições)  
**Para:** Extrair dados para análise

**Critérios de Aceite:**
- [ ] Endpoint `POST /api/v1/reports/export` cria job
- [ ] Tipos: CONSULTATIONS, PATIENTS, DOCTORS, PRESCRIPTIONS
- [ ] Formatos: JSON, CSV, PDF
- [ ] Parâmetros: data_inicio, data_fim, filtros
- [ ] Retorna 202 Accepted com job_id
- [ ] Job processado assincronamente por Celery
- [ ] Resultado armazenado em MinIO

**Estimativa:** 5 pontos  
**Prioridade:** MÉDIO  
**Status:** ✅ Completo

---

### 9.2 H-REPORT-002: Consultar Status do Relatório

**Como:** Médico, Administrador  
**Quero:** Verificar o status do relatório solicitado  
**Para:** Saber quando está pronto para download

**Critérios de Aceite:**
- [ ] Endpoint `GET /api/v1/reports/export/{jobId}` retorna status
- [ ] Status: PENDING, RUNNING, COMPLETED, FAILED
- [ ] Retorna 200 com status, row_count, s3_key
- [ ] Retorna 404 se job não existe

**Estimativa:** 2 pontos  
**Prioridade:** MÉDIO  
**Status:** ✅ Completo

---

### 9.3 H-REPORT-003: Download de Relatório

**Como:** Médico, Administrador  
**Quero:** Baixar arquivo do relatório  
**Para:** Usar dados em ferramentas externas

**Critérios de Aceite:**
- [ ] Endpoint `GET /api/v1/reports/export/{jobId}/download` retorna arquivo
- [ ] Arquivo é transferido do MinIO
- [ ] Content-Type correto (application/pdf, text/csv, application/json)
- [ ] Nome do arquivo legível
- [ ] Retorna 200 com stream do arquivo
- [ ] Retorna 404 se não existe
- [ ] Auditoria registra download

**Estimativa:** 3 pontos  
**Prioridade:** MÉDIO  
**Status:** ✅ Completo

---

### 9.4 H-REPORT-004: Dashboard com Métricas Operacionais

**Como:** Administrador  
**Quero:** Visualizar métricas operacionais (consultas/dia, pacientes, etc)  
**Para:** Monitorar operação

**Critérios de Aceite:**
- [ ] Endpoint `GET /api/v1/reports/summary` retorna resumo
- [ ] Métricas: total_consultations, total_patients, avg_wait_time
- [ ] Dados agregados por período (hoje, semana, mês)
- [ ] Retorna 200 com JSON de métricas
- [ ] Atualizado em tempo real ou cache 1h

**Estimativa:** 5 pontos  
**Prioridade:** MÉDIO  
**Status:** ✅ Completo

---

## 10. ÉPICO 9: OBSERVABILIDADE E AUDITORIA

### 10.1 H-OBS-001: Logs Estruturados de Requisições

**Como:** Operador  
**Quero:** Todos os eventos serem logados em formato estruturado  
**Para:** Diagnóstico e auditoria

**Critérios de Aceite:**
- [ ] Logs incluem: timestamp, service, request_id, user_id, path, status, duration
- [ ] Formato JSON enviado para Loki
- [ ] Request_id correlaciona logs entre serviços
- [ ] Retenção de 90 dias

**Estimativa:** 3 pontos  
**Prioridade:** ALTO  
**Status:** ✅ Completo (parcial)

---

### 10.2 H-OBS-002: Métricas de Prometheus

**Como:** Operador  
**Quero:** Coletar métricas de latência, taxa de erro, requests  
**Para:** Monitorar performance

**Critérios de Aceite:**
- [ ] Métricas: http_request_duration_ms, requests_total, errors_total
- [ ] Labels: service, endpoint, method, status
- [ ] Endpoint `/metrics` em cada serviço
- [ ] Scrape interval: 15s
- [ ] Retenção: 30 dias

**Estimativa:** 4 pontos  
**Prioridade:** ALTO  
**Status:** ✅ Completo (parcial)

---

### 10.3 H-OBS-003: Tracing Distribuído com Tempo

**Como:** Operador  
**Quero:** Rastrear requisição entre múltiplos serviços  
**Para:** Identificar gargalos de latência

**Critérios de Aceite:**
- [ ] Tracing via OpenTelemetry/Tempo
- [ ] Trace_id propagado entre serviços
- [ ] Spans incluem latência por serviço
- [ ] Retenção: 7 dias
- [ ] Dashboard em Grafana

**Estimativa:** 5 pontos  
**Prioridade:** MÉDIO  
**Status:** 📋 Planejado

---

### 10.4 H-OBS-004: Alertas Operacionais

**Como:** Operador  
**Quero:** Receber alertas em casos de anomalia  
**Para:** Responder rapidamente a problemas

**Critérios de Aceite:**
- [ ] Alertas: alta latência (>500ms), erro rate >1%, failed health checks
- [ ] Notificação via PagerDuty/Slack
- [ ] Silence duração configurável
- [ ] Alertas testáveis

**Estimativa:** 4 pontos  
**Prioridade:** MÉDIO  
**Status:** 📋 Planejado

---

## 11. Resumo de Cobertura

| Épico | Histórias | ✅ Completo | 📋 Planejado | Status Geral |
|-------|-----------|-----------|------------|-------------|
| 1. Autenticação | 5 | 3 | 2 | 60% |
| 2. Usuários | 5 | 1 | 4 | 20% |
| 3. Pacientes | 8 | 4 | 4 | 50% |
| 4. Agendamentos | 4 | 2 | 2 | 50% |
| 5. Prontuários | 4 | 2 | 2 | 50% |
| 6. Prescrições | 2 | 1 | 1 | 50% |
| 7. IA | 3 | 3 | 0 | 100% |
| 8. Relatórios | 4 | 4 | 0 | 100% |
| 9. Observabilidade | 4 | 2 | 2 | 50% |
| **TOTAL** | **39** | **22** | **17** | **56%** |

---

## 12. Priorização para Próximas Fases

### Fase 2 (Completar Funcionalidade Crítica)
1. ✅ H-USER-001 a H-USER-005 (Gestão de usuários)
2. ✅ H-PATIENT-004 a H-PATIENT-008 (Dados clínicos do paciente)
3. ✅ H-APPOINTMENT-002, H-APPOINTMENT-004 (Agendamento completo)

### Fase 3 (Completar Histórico e Auditoria)
1. ✅ H-RECORD-004 (Histórico de alterações)
2. ✅ H-OBS-003, H-OBS-004 (Tracing e alertas)
3. ✅ Auditoria completa (ETAPA_15)

---

## 13. Legenda

- **✅ Completo:** Feature implementada e testada
- **📋 Planejado:** Design aprovado, pronto para implementação
- **🔵 Em Progresso:** Desenvolvimento ativo
- **⭕ Não Iniciado:** Análise necessária

---

**Última atualização:** 14 de maio de 2026  
**Versão:** 1.0  
**Total de histórias:** 39  
**Cobertura:** 56% completo, 44% planejado
