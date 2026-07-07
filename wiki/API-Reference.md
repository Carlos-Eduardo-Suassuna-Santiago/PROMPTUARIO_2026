# API Reference

Base URL: `http://localhost:8000/api/v1`

Autenticação:
- Todos os endpoints (exceto `/auth/login`, `/auth/refresh`, `/auth/oauth/*`) exigem header:
  `Authorization: Bearer <access_token>`

Exemplos de grupos de endpoints (tabelas resumidas)

Auth
| Método | Path | Roles | Descrição | Request Body | Response |
|---|---|---:|---|---|---|
| POST | /auth/login | - | Login com email/senha | {email, password} | {access_token, refresh_token} |
| POST | /auth/refresh | - | Renovar token | {refresh_token} | {access_token, refresh_token} |
| GET | /auth/oauth/{provider} | - | Iniciar OAuth | - | redirect / oauth flow |

Patients
| Método | Path | Roles | Descrição | Request Body | Response |
|---|---|---:|---|---|---|
| POST | /patients | DOCTOR, ATTENDANT, ADMIN | Criar paciente | PatientCreate | Patient |
| GET | /patients/{id} | DOCTOR, ATTENDANT, PATIENT | Obter dados paciente | - | Patient |

Clinical
| Método | Path | Roles | Descrição | Request Body | Response |
|---|---|---:|---|---|---|
| POST | /appointments | DOCTOR, ATTENDANT, ADMIN | Agendar consulta | AppointmentCreate | Appointment |
| POST | /records | DOCTOR | Criar prontuário | MedicalRecordCreate | MedicalRecord |

AI
| Método | Path | Roles | Descrição | Request Body | Response |
|---|---|---:|---|---|---|
| POST | /ai/analyze | DOCTOR, ADMIN | Solicitar análise clínica | {record_id, patient_id, analysis_type} | {job_id} |
| GET | /ai/analysis/{job_id} | DOCTOR, ADMIN | Checar resultado | - | AnalysisCompleted |

Reporting/Admin
| Método | Path | Roles | Descrição | Request Body | Response |
|---|---|---:|---|---|---|
| POST | /reports | ADMIN | Criar job de relatório (async) | {type, filters, format} | {job_id} |
| GET | /reports/{job_id} | ADMIN | Status do job | - | {status, download_url?} |

Exemplos curl

Login:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@promptuario.health","password":"Admin@12345"}'
```

Criar paciente:
```bash
curl -X POST http://localhost:8000/api/v1/patients \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full_name":"João Silva","dob":"1980-05-01","email":"joao@example.com"}'
```

Agendar consulta:
```bash
curl -X POST http://localhost:8000/api/v1/appointments \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"pat_123","doctor_id":"doc_456","scheduled_at":"2026-07-10T10:00:00Z","type":"consulta"}'
```

Criar prontuário:
```bash
curl -X POST http://localhost:8000/api/v1/records \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"appointment_id":"app_789","chief_complaint":"dor de cabeça","diagnosis_codes":["G44.1"]}'
```

Solicitar análise IA:
```bash
curl -X POST http://localhost:8000/api/v1/ai/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"record_id":"rec_123","analysis_type":"drug_check"}'
```

Gerar relatório:
```bash
curl -X POST http://localhost:8000/api/v1/reports \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"type":"audit","format":"CSV","filters":{"service":"iam","from":"2026-01-01"}}'
```
