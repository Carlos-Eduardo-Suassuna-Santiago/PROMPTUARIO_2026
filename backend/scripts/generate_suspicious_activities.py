#!/usr/bin/env python3
"""
PROMPTUARIO — Script de Geração de Atividades Suspeitas para Auditoria
====================================================================
Este script gera registros realistas de auditoria (audit_logs) em múltiplos
bancos de dados (iam_db, patient_db e clinical_db) com comportamentos que
disparam os alertas automáticos do módulo de Auditoria e Segurança do PROMPTUARIO:

1. BRUTE_FORCE_ATTEMPT (Crítico):
   Mais de 5 falhas de login (AUTH_LOGIN_FAILED) para o mesmo e-mail nos
   últimos 7 dias. O script gera tentativas para contas estratégicas a partir
   de endereços IP externos suspeitos (ex: VPNs/Tor).

2. EXCESSIVE_DELETES (Alto):
   Mais de 10 operações de exclusão (DELETE) na mesma hora pelo mesmo usuário.
   O script gera exclusões em massa de prontuários, prescrições e pacientes
   a partir de IPs internos/comprometidos.

Execução (via Docker):
    docker compose exec reporting-service python /app/scripts/generate_suspicious_activities.py

Execução local:
    python backend/scripts/generate_suspicious_activities.py
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

try:
    import asyncpg
except ImportError:
    print("ERRO: O pacote 'asyncpg' é necessário para executar este script.")
    print("Instale com: pip install asyncpg")
    sys.exit(1)


# Configuração dos bancos de dados
DB_URLS = {
    "iam": os.getenv("IAM_DB_URL", "postgresql://iam:iam_pass@db-iam:5432/iam_db"),
    "patient": os.getenv("PATIENT_DB_URL", "postgresql://patient:patient_pass@db-patient:5432/patient_db"),
    "clinical": os.getenv("CLINICAL_DB_URL", "postgresql://clinical:clinical_pass@db-clinical:5432/clinical_db"),
}

# Suporte ao modo host local caso não esteja rodando dentro do container Docker
if not os.path.exists("/.dockerenv") and os.getenv("LOCAL_RUN", "false").lower() == "true":
    DB_URLS = {k: v.replace("@db-iam:", "@localhost:").replace("@db-patient:", "@localhost:").replace("@db-clinical:", "@localhost:") for k, v in DB_URLS.items()}


async def insert_logs(conn, logs: list[dict]):
    """Insere uma lista de registros na tabela audit_logs usando asyncpg."""
    query = """
        INSERT INTO audit_logs (
            id, service_name, table_name, operation, record_id,
            user_id, user_role, user_email, old_values, new_values,
            ip_address, request_id, timestamp
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
        )
    """
    batch = []
    for log in logs:
        batch.append((
            str(uuid.uuid4()),
            log.get("service_name", "unknown-service"),
            log.get("table_name", "unknown-table"),
            log.get("operation", "UPDATE"),
            log.get("record_id", str(uuid.uuid4())),
            log.get("user_id"),
            log.get("user_role"),
            log.get("user_email"),
            log.get("old_values"),
            log.get("new_values"),
            log.get("ip_address"),
            log.get("request_id", str(uuid.uuid4())),
            log.get("timestamp", datetime.now(timezone.utc)),
        ))
    await conn.executemany(query, batch)


async def generate_brute_force_attempts(conn_iam):
    """Gera tentativas de força bruta (múltiplos AUTH_LOGIN_FAILED no iam_db)."""
    now = datetime.now(timezone.utc)
    logs = []

    # Alerta 1: Ataque contra conta do Administrador do Sistema (IP Externo Suspeito)
    admin_email = "admin@promptuario.local"
    ip_attacker_1 = "185.220.101.45"  # IP proxy/tor de exemplo
    print(f"  [IAM DB] Gerando 14 falhas de login (Brute Force) para '{admin_email}' via IP {ip_attacker_1}...")
    for i in range(14):
        logs.append({
            "service_name": "iam-service",
            "table_name": "users",
            "operation": "AUTH_LOGIN_FAILED",
            "record_id": None,
            "user_id": None,
            "user_role": None,
            "user_email": admin_email,
            "old_values": None,
            "new_values": '{"reason": "Senha incorreta", "attempt": %d}' % (i + 1),
            "ip_address": ip_attacker_1,
            "timestamp": now - timedelta(minutes=(14 - i) * 2),
        })

    # Alerta 2: Ataque contra médico cardiologista (Outro IP Externo)
    doctor_email = "carlos.suassuna@promptuario.com.br"
    ip_attacker_2 = "45.148.10.22"
    print(f"  [IAM DB] Gerando 9 falhas de login (Brute Force) para '{doctor_email}' via IP {ip_attacker_2}...")
    for i in range(9):
        logs.append({
            "service_name": "iam-service",
            "table_name": "users",
            "operation": "AUTH_LOGIN_FAILED",
            "record_id": None,
            "user_id": None,
            "user_role": None,
            "user_email": doctor_email,
            "old_values": None,
            "new_values": '{"reason": "Credenciais inválidas", "attempt": %d}' % (i + 1),
            "ip_address": ip_attacker_2,
            "timestamp": now - timedelta(minutes=(9 - i) * 3),
        })

    await insert_logs(conn_iam, logs)


async def generate_excessive_deletes_patients(conn_patient):
    """Gera exclusões em massa em curto período de tempo no banco patient_db."""
    now = datetime.now(timezone.utc)
    logs = []

    # Alerta 3: Médico com conta comprometida excluindo fichas de pacientes
    doctor_id = "d9876543-21ab-cdef-0123-456789abcdef"
    doctor_email = "dr.comprometido@hospital.com.br"
    ip_compromised = "192.168.1.105"  # IP da rede local do hospital
    print(f"  [PATIENT DB] Gerando 15 exclusões em massa de pacientes na mesma hora pelo usuário '{doctor_email}' via IP {ip_compromised}...")
    
    for i in range(15):
        patient_id = str(uuid.uuid4())
        logs.append({
            "service_name": "patient-service",
            "table_name": "patients",
            "operation": "DELETE",
            "record_id": patient_id,
            "user_id": doctor_id,
            "user_role": "DOCTOR",
            "user_email": doctor_email,
            "old_values": '{"id": "%s", "full_name": "Paciente Removido %d", "status": "INACTIVE"}' % (patient_id, i + 1),
            "new_values": None,
            "ip_address": ip_compromised,
            "timestamp": now - timedelta(minutes=i * 2),
        })

    await insert_logs(conn_patient, logs)


async def generate_excessive_deletes_clinical(conn_clinical):
    """Gera exclusões em massa no banco clinical_db (prescrições e prontuários)."""
    now = datetime.now(timezone.utc)
    logs = []

    # Alerta 4: Atendente excluindo prescrições e registros clínicos no turno noturno
    attendant_id = "a1111111-22bb-33cc-44dd-555555555555"
    attendant_email = "atendente.noturno@hospital.com.br"
    ip_attendant = "10.0.0.88"
    print(f"  [CLINICAL DB] Gerando 12 exclusões de prescrições clínicas na mesma hora pelo usuário '{attendant_email}' via IP {ip_attendant}...")

    for i in range(12):
        prescription_id = str(uuid.uuid4())
        logs.append({
            "service_name": "clinical-service",
            "table_name": "prescriptions",
            "operation": "DELETE",
            "record_id": prescription_id,
            "user_id": attendant_id,
            "user_role": "ATTENDANT",
            "user_email": attendant_email,
            "old_values": '{"id": "%s", "medication": "Amoxicilina 500mg", "status": "REVOKED"}' % prescription_id,
            "new_values": None,
            "ip_address": ip_attendant,
            "timestamp": now - timedelta(minutes=i * 3),
        })

    await insert_logs(conn_clinical, logs)


async def main():
    print("=========================================================================")
    print("PROMPTUARIO — Gerador de Atividades Suspeitas para Auditoria")
    print("=========================================================================\n")

    for db_name, url in DB_URLS.items():
        print(f"→ Conectando ao banco de dados '{db_name}'...")
        try:
            conn = await asyncpg.connect(url)
            try:
                if db_name == "iam":
                    await generate_brute_force_attempts(conn)
                elif db_name == "patient":
                    await generate_excessive_deletes_patients(conn)
                elif db_name == "clinical":
                    await generate_excessive_deletes_clinical(conn)
            finally:
                await conn.close()
            print(f"  ✔ Registros injetados com sucesso em '{db_name}_db'!\n")
        except Exception as exc:
            print(f"  ✖ Falha ao conectar/injetar em '{db_name}': {exc}\n")

    print("=========================================================================")
    print("CONCLUSÃO:")
    print("Foram gerados 4 alertas de segurança críticos e de alta gravidade:")
    print("  1. BRUTE_FORCE_ATTEMPT (14 falhas)  — Alvo: admin@promptuario.local (IP: 185.220.101.45)")
    print("  2. BRUTE_FORCE_ATTEMPT (9 falhas)   — Alvo: carlos.suassuna@promptuario.com.br (IP: 45.148.10.22)")
    print("  3. EXCESSIVE_DELETES  (15 exclusões) — Autor: dr.comprometido@hospital.com.br (IP: 192.168.1.105)")
    print("  4. EXCESSIVE_DELETES  (12 exclusões) — Autor: atendente.noturno@hospital.com.br (IP: 10.0.0.88)")
    print("\nAcesse a aba 'Atividades Suspeitas' na página de Auditoria do sistema para visualizar!")
    print("=========================================================================")


if __name__ == "__main__":
    asyncio.run(main())
