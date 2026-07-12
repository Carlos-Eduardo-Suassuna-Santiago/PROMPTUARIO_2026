from __future__ import annotations

import json
import os
import time
from urllib import error, request

import pytest

try:
    from pymongo import MongoClient
except Exception:  # pragma: no cover
    MongoClient = None


API_BASE = os.getenv("PROMPTUARIO_API_BASE", "http://localhost:8000/api/v1")
MONGODB_URL = os.getenv(
    "PROMPTUARIO_MONGODB_URL",
    "mongodb://ai:ai_pass@localhost:27017/ai_db?authSource=admin",
)
ADMIN_EMAIL = os.getenv("PROMPTUARIO_ADMIN_EMAIL", "admin@promptuario.health")
ADMIN_PASSWORD = os.getenv("PROMPTUARIO_ADMIN_PASSWORD", "Admin@12345")


def http_json(method: str, url: str, body: dict | None = None, token: str | None = None, timeout: float = 15.0):
    headers = {"Accept": "application/json"}
    payload = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body).encode("utf-8")

    req = request.Request(url, method=method.upper(), data=payload, headers=headers)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            data = json.loads(raw) if raw else {"detail": exc.reason}
        except Exception:
            data = {"detail": raw or exc.reason}
        return exc.code, data


def wait_for_job(token: str, job_id: str, timeout_seconds: float = 45.0) -> dict:
    deadline = time.time() + timeout_seconds
    last = {}
    while time.time() < deadline:
        status, data = http_json("GET", f"{API_BASE}/ai/jobs/{job_id}", token=token)
        assert status == 200, f"Falha ao consultar job {job_id}: HTTP {status} {data}"
        last = data
        if data.get("status") in {"COMPLETED", "FAILED"}:
            return data
        time.sleep(1.0)
    raise AssertionError(f"Timeout aguardando job finalizar. Último estado: {last}")


def get_existing_patient_and_record(token: str) -> tuple[str, str | None]:
    status, patients = http_json("GET", f"{API_BASE}/patients?page=1&size=20", token=token)
    assert status == 200, f"Não foi possível listar pacientes: HTTP {status} {patients}"

    items = patients.get("items", [])
    assert items, "Banco sem pacientes para o teste de integração"

    for item in items:
        patient_user_id = item.get("user_id") or item.get("id")
        if not patient_user_id:
            continue

        status_r, records = http_json("GET", f"{API_BASE}/records/patient/{patient_user_id}", token=token)
        if status_r == 200:
            rec_items = records.get("items", [])
            if rec_items:
                record_id = rec_items[0].get("id")
                return patient_user_id, record_id

    first = items[0]
    return first.get("user_id") or first.get("id"), None


@pytest.mark.integration
def test_ai_analysis_flow_with_existing_database_data():
    if MongoClient is None:
        pytest.skip("pymongo não disponível no ambiente de teste")

    health_status, _ = http_json("GET", f"{API_BASE}/auth/oauth/providers", timeout=5.0)
    if health_status == 0:
        pytest.skip("Serviços HTTP não acessíveis em localhost:8000")

    login_status, login_resp = http_json(
        "POST",
        f"{API_BASE}/auth/login",
        body={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=10.0,
    )
    assert login_status == 200, f"Falha de login admin: HTTP {login_status} {login_resp}"
    token = login_resp["access_token"]

    patient_id, record_id = get_existing_patient_and_record(token)
    assert patient_id, "Não foi possível identificar patient_id para o teste"

    payload = {
        "analysis_type": "SYMPTOM_ANALYSIS",
        "patient_id": patient_id,
        "record_id": record_id,
        "context": {
            "chief_complaint": "dor de cabeça persistente",
            "anamnesis": "cefaleia há 3 dias com náusea leve",
        },
    }

    create_status, create_resp = http_json("POST", f"{API_BASE}/ai/analyze", body=payload, token=token)
    assert create_status == 202, f"Falha ao criar job de IA: HTTP {create_status} {create_resp}"

    job_id = create_resp.get("job_id")
    assert job_id, f"Resposta sem job_id: {create_resp}"

    job = wait_for_job(token, job_id)
    assert job["id"] == job_id
    assert job["analysis_type"] == "SYMPTOM_ANALYSIS"
    assert job["patient_id"] == patient_id
    assert job["status"] in {"COMPLETED", "FAILED"}

    mongo = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
    db = mongo.ai_db
    doc = db.analysis_jobs.find_one({"_id": job_id})
    assert doc is not None, "Job não persistido na coleção analysis_jobs"
    assert doc["patient_id"] == patient_id
    assert doc["analysis_type"] == "SYMPTOM_ANALYSIS"

    if record_id:
        list_status, list_resp = http_json("GET", f"{API_BASE}/ai/records/{record_id}/analyses", token=token)
        assert list_status == 200, f"Falha ao listar análises por prontuário: HTTP {list_status} {list_resp}"
        ids = {item.get("id") for item in list_resp.get("items", [])}
        assert job_id in ids, "Job criado não apareceu na listagem por prontuário"
