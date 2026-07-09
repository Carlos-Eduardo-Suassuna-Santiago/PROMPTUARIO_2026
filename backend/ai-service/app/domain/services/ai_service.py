from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time as _time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.domain.schemas import validate_llm_response
from shared.metrics import (
    ai_requests_total, ai_tokens_prompt_total, ai_tokens_completion_total,
    ai_request_duration_seconds, ai_cache_hits_total, ai_errors_total,
)

logger = logging.getLogger(__name__)


# ─── Explainability Helpers ───────────────────────────────────────────────────

def _build_explanation(analysis_type: str, result: dict, model: str, cached: bool = False) -> dict:
    """
    Build a human-readable explanation for the AI analysis result.
    This is stored alongside the result so the frontend can display it.
    """
    risk_level = result.get("risk_level", "UNKNOWN")
    risk_descriptions = {
        "LOW": "Baixo risco identificado. Nenhuma ação urgente necessária.",
        "MEDIUM": "Risco moderado. Recomenda-se avaliação médica.",
        "HIGH": "Risco alto. Atenção clínica necessária.",
        "CRITICAL": "Risco crítico. Intervenção imediata recomendada.",
        "UNKNOWN": "Não foi possível determinar o nível de risco.",
    }

    explanation_parts = [risk_descriptions.get(risk_level, "")]

    if analysis_type == "DRUG_INTERACTION_CHECK":
        interactions = result.get("interactions_found", [])
        conflicts = result.get("allergy_conflicts", [])
        if interactions:
            explanation_parts.append(
                f"Foram encontradas {len(interactions)} interação(ões) medicamentosa(s)."
            )
            for i, inter in enumerate(interactions[:3], 1):
                drugs = ", ".join(inter.get("drugs", []))
                explanation_parts.append(
                    f"  {i}. {drugs}: {inter.get('description', '')} (gravidade: {inter.get('severity', 'N/A')})"
                )
        if conflicts:
            explanation_parts.append(
                f"Foram identificados {len(conflicts)} conflito(s) com alergias."
            )
        if not interactions and not conflicts:
            explanation_parts.append("Nenhuma interação medicamentosa ou conflito com alergias identificado.")

    elif analysis_type == "SYMPTOM_ANALYSIS":
        diagnoses = result.get("possible_diagnoses", [])
        red_flags = result.get("red_flags", [])
        if diagnoses:
            explanation_parts.append(
                f"Foram considerados {len(diagnoses)} diagnóstico(s) diferencial(is)."
            )
        if red_flags:
            explanation_parts.append(
                f"Atenção: {len(red_flags)} bandeira(s) vermelha(s) identificada(s)."
            )

    elif analysis_type == "CLINICAL_SUMMARY":
        summary = result.get("summary", "")
        if summary:
            explanation_parts.append("Resumo clínico gerado com base nos dados fornecidos.")

    explanation_parts.append(
        "Esta análise é gerada por IA e não substitui a avaliação clínica do profissional de saúde."
    )

    return {
        "text": "\n".join(explanation_parts),
        "risk_level": risk_level,
        "risk_description": risk_descriptions.get(risk_level, ""),
        "model": model,
        "cached": cached,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _compute_cache_key(analysis_type: str, context: dict) -> str:
    """Compute a deterministic cache key from analysis type and context."""
    raw = json.dumps({"type": analysis_type, "context": context}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


# ─── AIService ────────────────────────────────────────────────────────────────

class AIService:
    def __init__(self, db, redis_client=None):
        self.db = db  # Motor AsyncIOMotorDatabase
        self.redis = redis_client
        self._llm_client: "LLMClient | None" = None

    def _get_llm_client(self) -> "LLMClient":
        """Lazy instantiation do LLMClient com as settings atuais."""
        if self._llm_client is None:
            from app.infrastructure.llm_client import LLMClient
            self._llm_client = LLMClient(
                api_key=settings.LLM_API_KEY,
                model=settings.LLM_MODEL,
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
                redis_client=self.redis,
            )
        return self._llm_client

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
            "explanation": None,
            "model_version": settings.LLM_MODEL,
            "attempts": 0,
            "latency_seconds": None,
            "cached": False,
            "error_message": None,
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

        start_time = _time.time()
        analysis_type = job["analysis_type"]
        model = settings.LLM_MODEL

        ai_requests_total.labels(
            service=settings.SERVICE_NAME, model=model, analysis_type=analysis_type
        ).inc()

        await self.db.analysis_jobs.update_one(
            {"_id": job_id}, {"$set": {"status": "RUNNING"}}
        )

        try:
            # Check cache first
            cache_key = _compute_cache_key(analysis_type, job.get("context", {}))
            cached_result = await self._get_cached_result(cache_key)

            if cached_result:
                result = cached_result
                cached = True
                ai_cache_hits_total.labels(
                    service=settings.SERVICE_NAME, analysis_type=analysis_type
                ).inc()
                logger.info("Cache hit for analysis %s (key=%s)", job_id, cache_key[:16])
            else:
                # Run analysis with timeout
                try:
                    result = await asyncio.wait_for(
                        self._dispatch(job),
                        timeout=settings.ANALYSIS_TIMEOUT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    raise TimeoutError(
                        f"Analysis timed out after {settings.ANALYSIS_TIMEOUT_SECONDS}s"
                    )

                cached = False
                # Cache the result
                await self._set_cached_result(cache_key, result)

            duration = _time.time() - start_time
            ai_request_duration_seconds.labels(
                service=settings.SERVICE_NAME, model=model, analysis_type=analysis_type
            ).observe(duration)

            # Build explanation
            explanation = _build_explanation(analysis_type, result, model, cached=cached)

            update = {
                "status": "COMPLETED",
                "result": result,
                "risk_level": result.get("risk_level", "UNKNOWN"),
                "explanation": explanation,
                "model_version": model,
                "attempts": 1,
                "latency_seconds": duration,
                "cached": cached,
                "error_message": None,
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
                        analysis_type=analysis_type,
                        risk_level=result.get("risk_level", "UNKNOWN"),
                        result=result,
                        model_version=model,
                    )
                )
            job.update(update)
            return job

        except asyncio.TimeoutError as e:
            duration = _time.time() - start_time
            error_msg = str(e)
            ai_errors_total.labels(
                service=settings.SERVICE_NAME, error_type="TimeoutError"
            ).inc()
            logger.error("Analysis timeout for job %s: %s", job_id, error_msg)
            await self.db.analysis_jobs.update_one(
                {"_id": job_id},
                {
                    "$set": {
                        "status": "FAILED",
                        "error_message": error_msg,
                        "latency_seconds": duration,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
            )
            raise

        except Exception as e:
            duration = _time.time() - start_time
            error_msg = f"{type(e).__name__}: {str(e)}"
            ai_errors_total.labels(
                service=settings.SERVICE_NAME, error_type=type(e).__name__
            ).inc()
            logger.error("Analysis failed for job %s: %s", job_id, error_msg)
            await self.db.analysis_jobs.update_one(
                {"_id": job_id},
                {
                    "$set": {
                        "status": "FAILED",
                        "error_message": error_msg,
                        "latency_seconds": duration,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
            )
            raise

    async def _get_cached_result(self, cache_key: str) -> dict | None:
        """Check Redis for a cached analysis result."""
        if not self.redis or not settings.CACHE_ENABLED:
            return None
        try:
            cached = await self.redis.get(f"analysis_cache:{cache_key}")
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning("Cache read error: %s", e)
        return None

    async def _set_cached_result(self, cache_key: str, result: dict) -> None:
        """Store analysis result in Redis cache."""
        if not self.redis or not settings.CACHE_ENABLED:
            return
        try:
            await self.redis.setex(
                f"analysis_cache:{cache_key}",
                settings.LLM_CACHE_TTL_SECONDS,
                json.dumps(result),
            )
        except Exception as e:
            logger.warning("Cache write error: %s", e)

    async def _dispatch(self, job: dict) -> dict:
        """Route to appropriate analysis handler with schema validation."""
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
                "key_points": [],
                "disclaimer": "Análise simulada",
            }
        prompt = _build_summary_prompt(context)
        return await self._call_llm(prompt, schema="clinical_summary")

    async def _call_llm(self, prompt: str, schema: str) -> dict:
        """
        Chama a LLM com circuit breaker, retry, cache e validação de schema.
        Em caso de falha ou ausência de API key, retorna mock response.
        """
        from app.infrastructure.llm_client import CircuitOpenError, LLMResponseValidationError

        system_prompt = (
            "Você é um assistente médico de suporte à decisão clínica. "
            "Responda APENAS em JSON válido conforme o schema solicitado. "
            "Não adicione texto fora do JSON. "
            "IMPORTANTE: Esta é uma ferramenta de apoio — o médico tem a decisão final."
        )

        client = self._get_llm_client()

        try:
            result = await client.call(prompt, system_prompt, schema_name=schema)
            if result is None:
                # Sem API key — modo mock
                logger.info("LLM em modo mock (LLM_API_KEY não configurada)")
                return self._mock_response(schema)
            return result

        except LLMResponseValidationError as exc:
            logger.warning("LLM response validation failed: %s — usando mock", exc)
            return self._mock_response(schema)

        except CircuitOpenError as exc:
            logger.warning("Circuit breaker OPEN: %s — usando mock", exc)
            return self._mock_response(schema)

        except Exception as exc:
            logger.error("Falha na chamada LLM após retries: %s — usando mock", exc)
            return self._mock_response(schema)

    def _mock_response(self, schema: str) -> dict:
        """Resposta simulada quando LLM não está disponível."""
        base = {
            "disclaimer": "Análise simulada — LLM não disponível ou não configurada",
        }
        if schema == "drug_interaction":
            return {**base, "risk_level": "UNKNOWN", "interactions_found": [],
                    "allergy_conflicts": [], "recommendations": []}
        elif schema == "symptom_analysis":
            return {**base, "risk_level": "UNKNOWN", "possible_diagnoses": [],
                    "recommended_exams": [], "red_flags": []}
        elif schema == "clinical_summary":
            return {**base, "risk_level": "UNKNOWN", "summary": "Resumo indisponível", "key_points": []}
        return base


# ─── Prompt Builders ──────────────────────────────────────────────────────────

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
    {{"drugs": ["drug_a", "drug_b"], "severity": "LOW|MEDIUM|HIGH|CRITICAL", "description": "..."}}
  ],
  "allergy_conflicts": [
    {{"medication": "...", "allergen": "...", "risk": "LOW|MEDIUM|HIGH|CRITICAL"}}
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

Retorne JSON:
{{
  "risk_level": "LOW|MEDIUM|HIGH",
  "summary": "Resumo clínico detalhado...",
  "key_points": ["..."],
  "disclaimer": "Ferramenta de apoio — decisão final é do médico"
}}
"""