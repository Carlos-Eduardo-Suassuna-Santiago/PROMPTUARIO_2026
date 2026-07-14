#!/usr/bin/env python3
"""
PROMPTUARIO — Script para criar prontuários das consultas confirmadas
====================================================================
Este script conecta no banco de dados clinical_db, busca todas as consultas
com status CONFIRMED ou COMPLETED que ainda não possuem prontuário e 
gera um prontuário (MedicalRecord) automático para elas.

Execução (via Docker):
    docker compose exec clinical-service python /app/scripts/generate_confirmed_records.py
"""

import asyncio
import os
import sys
import uuid
import json
from datetime import datetime, timezone

try:
    import asyncpg
except ImportError:
    print("ERRO: O pacote 'asyncpg' é necessário para executar este script.")
    print("Instale com: pip install asyncpg")
    sys.exit(1)


# URL do banco de dados Clínico
DB_URL = os.getenv("CLINICAL_DB_URL", "postgresql://clinical:clinical_pass@db-clinical:5432/clinical_db")

# Suporte ao modo host local caso não esteja rodando dentro do container Docker
if not os.path.exists("/.dockerenv") and os.getenv("LOCAL_RUN", "false").lower() == "true":
    DB_URL = DB_URL.replace("@db-clinical:", "@localhost:")


async def generate_records():
    print(f"Conectando ao banco de dados: {DB_URL}")
    try:
        conn = await asyncpg.connect(DB_URL)
    except Exception as e:
        print(f"Erro ao conectar no banco de dados: {e}")
        return

    # Buscar todas as consultas que não possuem prontuário
    query_appointments = """
        SELECT a.id, a.patient_id, a.doctor_id
        FROM appointments a
        LEFT JOIN medical_records mr ON a.id = mr.appointment_id
        WHERE a.status IN ('CONFIRMED', 'COMPLETED') AND mr.id IS NULL
    """
    appointments = await conn.fetch(query_appointments)
    
    if not appointments:
        print("Nenhuma consulta sem prontuário encontrada.")
        await conn.close()
        return

    print(f"Encontradas {len(appointments)} consultas sem prontuário. Criando...")

    query_insert_record = """
        INSERT INTO medical_records (
            id, appointment_id, patient_id, doctor_id, 
            chief_complaint, anamnesis, physical_exam, diagnosis, diagnosis_codes,
            treatment_plan, observations, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10, $11, $12, $13
        )
    """

    now = datetime.now(timezone.utc)
    batch = []
    
    # Criar um audit log para a criação
    query_insert_history = """
        INSERT INTO medical_record_history (
            id, record_id, changed_by, changes, created_at
        ) VALUES (
            $1, $2, $3, $4::jsonb, $5
        )
    """
    history_batch = []

    for appt in appointments:
        record_id = str(uuid.uuid4())
        batch.append((
            record_id,
            appt['id'],
            appt['patient_id'],
            appt['doctor_id'],
            "Consulta de rotina (gerado via script de migração)", # chief_complaint
            "Paciente relata sintomas estáveis.", # anamnesis
            "Bom estado geral.", # physical_exam
            "Nenhuma alteração aguda.", # diagnosis
            "[]", # diagnosis_codes (jsonb)
            "Manter acompanhamento clínico.", # treatment_plan
            "Prontuário gerado automaticamente.", # observations
            now,
            now
        ))
        
        history_batch.append((
            str(uuid.uuid4()),
            record_id,
            appt['doctor_id'],
            json.dumps({"action": "created_by_script"}),
            now
        ))

    async with conn.transaction():
        await conn.executemany(query_insert_record, batch)
        await conn.executemany(query_insert_history, history_batch)

    print(f"Sucesso! {len(batch)} prontuários foram criados e associados às consultas.")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(generate_records())
