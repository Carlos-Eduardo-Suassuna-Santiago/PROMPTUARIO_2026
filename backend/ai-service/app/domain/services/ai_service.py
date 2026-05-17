from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class AnalysisJob:
    """In-memory model (persisted to MongoDB)."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class AIService:
    def __init__(self, db, redis_client=None):
        self.db = db  # Motor AsyncIOMotorDatabase
        self.redis = redis_client

    async def create_job(
        self,
        analysis_type: str,
        patient_id: str,
        record_id: str | None = None,
        context: dict | None = None,
    ) -> dict:
        job = {
            "_id": str(uuid.uuid4()),
            "analysis_type": analysis_type,
            "patient_id": patient_id,
            "record_id": record_id,
            "context": context or {},
            "status": "PENDING",
            "result": None,
            "risk_level": None,
            "model_version": settings.LLM_MODEL,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
        }
        await self.db.analysis_jobs.insert_one(job)
        return job

    async def get_job(self, job_id: str) -> dict | None:
        return await self.db.analysis_jobs.find_one({"_id": job_id})

    async def list_by_record(self, record_id: str) -> list[dict]:
        cursor = self.db.analysis_jobs.find({"record_id": record_id}).sort("created_at", -1)
        return await cursor.to_list(length=50)

    async def run_analysis(self, job_id: str, publisher=None) -> dict:
        job = await self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        await self.db.analysis_jobs.update_one(
            {"_id": job_id}, {"$set": {"status": "RUNNING"}}
        )

        try:
            result = await self._dispatch(job)
            update = {
                "status": "COMPLETED",
                "result": result,
                "risk_level": result.get("risk_level", "UNKNOWN"),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            await self.db.analysis_jobs.update_one({"_id": job_id}, {"$set": update})

            # Publish AnalysisCompleted event
            if publisher:
                from shared.events import AnalysisCompletedEvent
                await publisher.publish(
                    AnalysisCompletedEvent(
                        job_id=job_id,
                        record_id=job.get("record_id"),
                        patient_id=job["patient_id"],
                        analysis_type=job["analysis_type"],
                        risk_level=result.get("risk_level", "UNKNOWN"),
                        result=result,
                        model_version=settings.LLM_MODEL,
                    )
                )
            job.update(update)
            return job

        except Exception as e:
            logger.error("Analysis failed for job %s: %s", job_id, e)
            await self.db.analysis_jobs.update_one(
                {"_id": job_id},
                {"$set": {"status": "FAILED", "error": str(e)}},
            )
            raise

    async def _dispatch(self, job: dict) -> dict:
        """Route to appropriate analysis handler."""
        analysis_type = job["analysis_type"]
        context = job.get("context", {})

        if analysis_type == "DRUG_INTERACTION_CHECK":
            return await self._check_drug_interactions(context)
        elif analysis_type == "SYMPTOM_ANALYSIS":
            return await self._analyze_symptoms(context)
        elif analysis_type == "CLINICAL_SUMMARY":
            return await self._generate_clinical_summary(context)
        else:
            raise ValueError(f"Unknown analysis type: {analysis_type}")

    async def _check_drug_interactions(self, context: dict) -> dict:
        medications = context.get("medications", [])
        allergies = context.get("allergies", [])

        if not settings.LLM_API_KEY:
            # Mock response for development without API key
            return {
                "risk_level": "LOW",
                "interactions_found": [],
                "allergy_conflicts": [],
                "recommendations": ["Monitorar pressão arterial", "Tomar com alimentos"],
                "disclaimer": "Análise simulada — configure LLM_API_KEY para análise real",
            }

        prompt = _build_drug_interaction_prompt(medications, allergies)
        return await self._call_llm(prompt, schema="drug_interaction")

    async def _analyze_symptoms(self, context: dict) -> dict:
        chief_complaint = context.get("chief_complaint", "")
        anamnesis = context.get("anamnesis", "")

        if not settings.LLM_API_KEY:
            return {
                "risk_level": "MEDIUM",
                "possible_diagnoses": ["A investigar"],
                "recommended_exams": [],
                "red_flags": [],
                "disclaimer": "Análise simulada — configure LLM_API_KEY para análise real",
            }

        prompt = _build_symptom_prompt(chief_complaint, anamnesis)
        return await self._call_llm(prompt, schema="symptom_analysis")

    async def _generate_clinical_summary(self, context: dict) -> dict:
        if not settings.LLM_API_KEY:
            return {
                "risk_level": "LOW",
                "summary": "Resumo clínico simulado",
                "disclaimer": "Análise simulada",
            }
        prompt = _build_summary_prompt(context)
        return await self._call_llm(prompt, schema="clinical_summary")

    async def _call_llm(self, prompt: str, schema: str) -> dict:
        """Call OpenAI-compatible API."""
        import httpx

        system_prompt = (
            "Você é um assistente médico de suporte à decisão clínica. "
            "Responda APENAS em JSON válido conforme o schema solicitado. "
            "Não adicione texto fora do JSON. "
            "IMPORTANTE: Esta é uma ferramenta de apoio — o médico tem a decisão final."
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.LLM_MODEL,
                    "max_tokens": settings.LLM_MAX_TOKENS,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(content)


def _build_drug_interaction_prompt(medications: list, allergies: list) -> str:
    return f"""
Analise as seguintes medicações para interações medicamentosas e conflitos com alergias.

Medicações prescritas:
{json.dumps(medications, indent=2, ensure_ascii=False)}

Alergias conhecidas do paciente:
{json.dumps(allergies, indent=2, ensure_ascii=False)}

Retorne um JSON com o seguinte schema:
{{
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "interactions_found": [
    {{"drugs": ["drug_a", "drug_b"], "severity": "...", "description": "..."}}
  ],
  "allergy_conflicts": [
    {{"medication": "...", "allergen": "...", "risk": "..."}}
  ],
  "recommendations": ["..."],
  "disclaimer": "Ferramenta de apoio — decisão final é do médico"
}}
"""


def _build_symptom_prompt(chief_complaint: str, anamnesis: str) -> str:
    return f"""
Analise os sintomas clínicos e sugira diagnósticos diferenciais.

Queixa principal: {chief_complaint}
Anamnese: {anamnesis}

Retorne um JSON com o seguinte schema:
{{
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "possible_diagnoses": ["..."],
  "recommended_exams": ["..."],
  "red_flags": ["..."],
  "disclaimer": "Ferramenta de apoio — decisão final é do médico"
}}
"""


def _build_summary_prompt(context: dict) -> str:
    return f"""
Gere um resumo clínico objetivo para o seguinte contexto:
{json.dumps(context, indent=2, ensure_ascii=False)}

Retorne JSON: {{"risk_level": "LOW|MEDIUM|HIGH", "summary": "...", "key_points": ["..."]}}
"""
