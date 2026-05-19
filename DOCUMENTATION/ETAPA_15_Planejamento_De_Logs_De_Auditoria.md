# ETAPA 15 — PLANEJAMENTO DE LOGS DE AUDITORIA PARA OPERAÇÕES DE BANCO DE DADOS

Este documento define a estratégia de implementação de auditoria para operações sensíveis de banco de dados no PROMPTUARIO Backend.

---

## 1. Objetivo

Implementar um sistema de logs de auditoria que permita rastreabilidade completa de operações críticas, conformidade regulatória (LGPD, segurança), diagnóstico de problemas e investigação de incidentes.

---

## 2. Princípios de Auditoria

- **Imutabilidade:** Registros de auditoria nunca devem ser alterados ou deletados.
- **Contexto completo:** Cada log deve conter quem fez, quando, o quê e por quê.
- **Não-repúdio:** Operações devem ser rastreáveis ao usuário responsável.
- **Retenção:** Manter histórico por período definido por política de conformidade.
- **Integração:** Logs devem fluir para Loki e ferramentas de observabilidade.
- **Performance:** Não impactar latência das operações críticas.

---

## 3. Operações a Serem Auditadas

### 3.1 IAM Service

| Operação | Entidade | Dados a Registrar | Nível de Risco |
|----------|----------|------------------|----------------|
| CREATE | users | user_id, email, role, created_by | ALTO |
| UPDATE | users | user_id, email, role, fields_changed, changed_by | ALTO |
| DELETE | users | user_id, deleted_by, deactivation_reason | ALTO |
| LOGIN | users | user_id, email, ip_address, timestamp, success/failure | MÉDIO |
| LOGOUT | users | user_id, email, timestamp | MÉDIO |
| TOKEN_ISSUE | refresh_tokens | user_id, expires_at, issuer | MÉDIO |
| TOKEN_REVOKE | refresh_tokens | user_id, revoked_by, reason | MÉDIO |
| PASSWORD_CHANGE | users | user_id, changed_by, timestamp | ALTO |

### 3.2 Patient Service

| Operação | Entidade | Dados a Registrar | Nível de Risco |
|----------|----------|------------------|----------------|
| CREATE | patients | patient_id, user_id, created_by | ALTO |
| UPDATE | patients | patient_id, fields_changed, updated_by | ALTO |
| DELETE/ANONYMIZE | patients | patient_id, deleted_by, reason (LGPD) | CRÍTICO |
| ADD | allergies | patient_id, substance, severity, added_by | MÉDIO |
| UPDATE | allergies | allergy_id, changes, updated_by | MÉDIO |
| REMOVE | allergies | allergy_id, removed_by, reason | MÉDIO |
| ADD | vaccines | patient_id, vaccine_name, added_by | MÉDIO |
| ADD | medications | patient_id, medication_name, added_by | MÉDIO |

### 3.3 Clinical Service

| Operação | Entidade | Dados a Registrar | Nível de Risco |
|----------|----------|------------------|----------------|
| CREATE | appointments | appointment_id, patient_id, doctor_id, created_by | MÉDIO |
| UPDATE | appointments | appointment_id, status_change, updated_by | MÉDIO |
| CANCEL | appointments | appointment_id, reason, cancelled_by | MÉDIO |
| CREATE | medical_records | record_id, appointment_id, doctor_id, created_by | CRÍTICO |
| UPDATE | medical_records | record_id, diagnosis, treatment_plan, updated_by | CRÍTICO |
| CREATE | prescriptions | prescription_id, medications, doctor_id, created_by | CRÍTICO |
| CREATE | exam_requests | exam_id, exam_type, urgency, created_by | MÉDIO |

### 3.4 Reporting Service

| Operação | Entidade | Dados a Registrar | Nível de Risco |
|----------|----------|------------------|----------------|
| CREATE | report_jobs | job_id, report_type, parameters, requested_by | MÉDIO |
| COMPLETE | report_jobs | job_id, result_rows, output_format, completed_at | MÉDIO |
| FAIL | report_jobs | job_id, error_reason | MÉDIO |
| DOWNLOAD | report_jobs | job_id, downloaded_by, ip_address, timestamp | MÉDIO |

### 3.5 AI Service

| Operação | Entidade | Dados a Registrar | Nível de Risco |
|----------|----------|------------------|----------------|
| CREATE | analysis_jobs | job_id, analysis_type, patient_id, created_by | MÉDIO |
| COMPLETE | analysis_jobs | job_id, result_summary, risk_level | MÉDIO |
| FAIL | analysis_jobs | job_id, error_reason | MÉDIO |

---

## 4. Estratégia de Implementação

### 4.1 Padrão de Auditoria por Serviço

Cada serviço implementará auditoria seguindo este padrão:

#### 4.1.1 Tabela de Auditoria Local

```sql
CREATE TABLE service_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operation VARCHAR(50) NOT NULL,       -- CREATE, UPDATE, DELETE, LOGIN, etc.
    entity_type VARCHAR(100) NOT NULL,    -- users, patients, medical_records, etc.
    entity_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    old_values JSONB,                     -- Valores anteriores (UPDATE/DELETE)
    new_values JSONB,                     -- Valores novos (CREATE/UPDATE)
    ip_address INET,
    user_agent TEXT,
    status VARCHAR(20) NOT NULL,          -- SUCCESS, FAILURE
    error_reason TEXT,
    request_id UUID,                      -- Correlação com logs
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB                        -- Campo extensível
);

CREATE INDEX idx_service_audit_user ON service_audit_logs(user_id, timestamp DESC);
CREATE INDEX idx_service_audit_entity ON service_audit_logs(entity_type, entity_id, timestamp DESC);
```

#### 4.1.2 Middleware de Auditoria

```python
# shared/middleware/audit.py

class AuditMiddleware:
    async def __call__(self, request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.user_id = extract_user_id_from_jwt(request)
        request.state.ip_address = request.client.host
        
        start_time = time.time()
        response = await call_next(request)
        elapsed = time.time() - start_time
        
        # Log estruturado para Loki
        audit_logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "user_id": request.state.user_id,
                "status_code": response.status_code,
                "elapsed_ms": int(elapsed * 1000),
            }
        )
        
        return response
```

#### 4.1.3 Decorador para Captura Automática

```python
# shared/audit/decorators.py

def audit_operation(
    operation: str,
    entity_type: str,
    capture_old: bool = False,
    capture_new: bool = True
):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Capturar antes (se UPDATE/DELETE)
            old_values = None
            if capture_old and 'entity_id' in kwargs:
                old_values = await fetch_entity(entity_type, kwargs['entity_id'])
            
            # Executar operação
            try:
                result = await func(*args, **kwargs)
                status = "SUCCESS"
                error_reason = None
            except Exception as e:
                status = "FAILURE"
                error_reason = str(e)
                raise
            finally:
                # Registrar auditoria
                await audit_service.log(
                    operation=operation,
                    entity_type=entity_type,
                    entity_id=kwargs.get('entity_id'),
                    user_id=get_current_user_id(),
                    old_values=old_values,
                    new_values=result if status == "SUCCESS" else None,
                    ip_address=get_client_ip(),
                    status=status,
                    error_reason=error_reason,
                    request_id=get_request_id(),
                )
            
            return result
        return wrapper
    return decorator
```

### 4.2 Integração com Observabilidade

#### 4.2.1 Loki (Logs Centralizados)

Todos os logs de auditoria devem incluir labels estruturados:

```yaml
# Loki scrape config
relabel_configs:
  - source_labels: [service]
    target_label: job
  - source_labels: [operation]
    target_label: audit_operation
  - source_labels: [entity_type]
    target_label: audit_entity
```

Query exemplo em Grafana:
```logql
{job="iam-service", audit_operation="CREATE"} |= "users" | json | select_by_labels(user_id, timestamp)
```

#### 4.2.2 Prometheus (Métricas de Auditoria)

```python
# shared/metrics/audit_metrics.py

audit_operations_total = Counter(
    'audit_operations_total',
    'Total audit operations',
    ['service', 'operation', 'entity_type', 'status']
)

audit_operation_duration = Histogram(
    'audit_operation_duration_seconds',
    'Duration of audit operations',
    ['service', 'operation']
)
```

#### 4.2.3 Alertas

```yaml
# prometheus/alerts.yml

groups:
  - name: audit_alerts
    rules:
      - alert: AuditLogWriteFailure
        expr: rate(audit_write_errors_total[5m]) > 0
        for: 5m
        annotations:
          summary: "Audit logging failure detected"
      
      - alert: SuspiciousAuthenticationActivity
        expr: rate(audit_operations_total{operation="LOGIN", status="FAILURE"}[1m]) > 10
        for: 2m
        annotations:
          summary: "Multiple failed login attempts"
```

---

## 5. Estrutura de Log de Auditoria

### 5.1 Formato JSON para Loki/ELK

```json
{
  "timestamp": "2026-05-11T10:30:45.123Z",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "service": "clinical-service",
  "operation": "CREATE",
  "entity_type": "medical_records",
  "entity_id": "med-001",
  "user_id": "usr-doc-001",
  "user_role": "DOCTOR",
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "status": "SUCCESS",
  "old_values": null,
  "new_values": {
    "id": "med-001",
    "appointment_id": "apt-001",
    "chief_complaint": "Dor de cabeça",
    "diagnosis": "Enxaqueca"
  },
  "duration_ms": 145,
  "error_reason": null,
  "metadata": {
    "affected_entities": ["patient:pat-001"],
    "data_classification": "SENSITIVE"
  }
}
```

### 5.2 Retenção de Logs

| Tipo de Operação | Retenção | Motivo |
|------------------|----------|--------|
| CREATE/UPDATE/DELETE críticos | 7 anos | LGPD, conformidade |
| LOGIN/LOGOUT | 1 ano | Segurança, auditoria |
| READ (se houver) | 90 dias | Diagnóstico |
| Dados pessoais deletados | 7 anos | Rastreabilidade de LGPD |

---

## 6. Plano de Implementação

### Fase 1 — Fundação (Semana 1-2)

- [ ] Criar modelo genérico de auditoria em `shared/audit/`
- [ ] Implementar middleware de captura de contexto
- [ ] Criar tabelas `*_audit_logs` em cada banco
- [ ] Integrar Loki com stdout estruturado

### Fase 2 — Clinical Service (Semana 3-4)

- [ ] Implementar decorador `@audit_operation` em medical_records
- [ ] Implementar decorador em appointments
- [ ] Implementar decorador em prescriptions
- [ ] Testar integração com Loki
- [ ] Validar retenção de 7 anos em PostgreSQL

### Fase 3 — IAM Service (Semana 5)

- [ ] Implementar auditoria em users (CREATE, UPDATE, DELETE)
- [ ] Implementar auditoria de LOGIN/LOGOUT/PASSWORD_CHANGE
- [ ] Integrar com Redis para rastreamento de sessão

### Fase 4 — Patient Service (Semana 6)

- [ ] Implementar auditoria de pacientes
- [ ] Implementar rastreamento de LGPD (anonymization)
- [ ] Testes de conformidade

### Fase 5 — Reporting & AI Services (Semana 7)

- [ ] Implementar auditoria de jobs
- [ ] Testes de performance

### Fase 6 — Dashboards & Compliance (Semana 8)

- [ ] Criar dashboards em Grafana
- [ ] Implementar relatórios de conformidade
- [ ] Testes de segurança e penetração

---

## 7. Formato de Resposta do Endpoint de History

```http
GET /api/v1/records/{recordId}/history HTTP/1.1
Authorization: Bearer <JWT>

HTTP/1.1 200 OK
Content-Type: application/json

{
  "data": [
    {
      "id": "hist-001",
      "record_id": "med-001",
      "operation": "CREATED",
      "changed_by": "usr-doc-001",
      "changed_by_name": "Dr. Silva",
      "timestamp": "2026-05-11T09:30:00Z",
      "snapshot": {
        "chief_complaint": "Dor de cabeça",
        "diagnosis": "Enxaqueca"
      }
    },
    {
      "id": "hist-002",
      "record_id": "med-001",
      "operation": "UPDATED",
      "changed_by": "usr-doc-002",
      "changed_by_name": "Dr. Santos",
      "timestamp": "2026-05-11T10:15:00Z",
      "snapshot": {
        "treatment_plan": "Repouso e analgésico"
      }
    }
  ],
  "meta": {
    "total": 2,
    "page": 1
  }
}
```

---

## 8. Conformidade e Segurança

### 8.1 LGPD (Lei Geral de Proteção de Dados)

- Logs contêm identificadores de usuário e podem conter dados sensíveis.
- Acesso restrito a usuários ADMIN e auditores.
- Direito ao esquecimento: anonimizar logs de usuários deletados (mascarar IDs).
- Retenção máxima de 7 anos, com destruição controlada.

### 8.2 Criptografia em Trânsito e em Repouso

- TLS 1.3 para transmissão de logs.
- Criptografia de banco (pgcrypto para PostgreSQL).
- Backup encriptado de logs de auditoria.

### 8.3 Controle de Acesso

- Apenas ADMIN ou auditores autorizados acessam históricos.
- Logs de quem acessou os logs de auditoria (meta-auditoria).

---

## 9. Métricas de Sucesso

- 100% das operações críticas auditadas.
- Latência de auditoria < 5ms por operação.
- Retenção de logs conforme política (7 anos).
- Alertas de anomalias configurados e testados.
- Conformidade validada por audit externo.

---

## 10. Próximas Etapas

1. **Aprovação do design.**
2. **Implementação incremental por serviço.**
3. **Testes de penetração e conformidade.**
4. **Documentação de operação e manutenção.**
5. **Treinamento de equipe.**

---

**Última atualização:** 11 de maio de 2026  
**Versão:** 1.0  
**Escopo:** Planejamento de auditoria para operações críticas de banco de dados
