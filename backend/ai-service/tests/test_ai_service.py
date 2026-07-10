"""
Tests for AI Service: explainability, cache, timeout, mock fallback, job lifecycle.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings
from app.domain.services.ai_service import (
    AIService,
    _build_explanation,
    _compute_cache_key,
)


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.analysis_jobs = AsyncMock()
    db.analysis_jobs.insert_one = AsyncMock()
    db.analysis_jobs.find_one = AsyncMock()
    db.analysis_jobs.update_one = AsyncMock()
    db.analysis_jobs.find = MagicMock()
    return db


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()
    return redis


@pytest.fixture
def ai_service(mock_db, mock_redis):
    return AIService(mock_db, mock_redis)


# ─── Explainability ──────────────────────────────────────────────────────────

class TestExplainability:
    def test_build_explanation_drug_interaction_with_findings(self):
        """Should build detailed explanation for drug interaction with findings."""
        result = {
            "risk_level": "HIGH",
            "interactions_found": [
                {
                    "drugs": ["Losartana", "Ibuprofeno"],
                    "severity": "HIGH",
                    "description": "Aumento do risco de insuficiência renal",
                }
            ],
            "allergy_conflicts": [
                {"medication": "Amoxicilina", "allergen": "Penicilina", "risk": "CRITICAL"}
            ],
            "recommendations": ["Suspender Ibuprofeno"],
        }
        explanation = _build_explanation("DRUG_INTERACTION_CHECK", result, "gpt-4o-mini")
        assert explanation["risk_level"] == "HIGH"
        assert "1 interação" in explanation["text"]
        assert "Losartana" in explanation["text"]
        assert "Ibuprofeno" in explanation["text"]
        assert "1 conflito" in explanation["text"]
        assert explanation["cached"] is False
        assert explanation["model"] == "gpt-4o-mini"

    def test_build_explanation_drug_interaction_no_findings(self):
        """Should indicate no interactions found."""
        result = {
            "risk_level": "LOW",
            "interactions_found": [],
            "allergy_conflicts": [],
            "recommendations": [],
        }
        explanation = _build_explanation("DRUG_INTERACTION_CHECK", result, "gpt-4o-mini")
        assert "Nenhuma interação" in explanation["text"]

    def test_build_explanation_symptom_analysis(self):
        """Should build explanation for symptom analysis."""
        result = {
            "risk_level": "MEDIUM",
            "possible_diagnoses": ["Enxaqueca", "Cefaleia tensional"],
            "recommended_exams": ["TC crânio"],
            "red_flags": ["Piora progressiva"],
        }
        explanation = _build_explanation("SYMPTOM_ANALYSIS", result, "gpt-4o-mini")
        assert "2 diagnóstico" in explanation["text"]
        assert "1 bandeira" in explanation["text"]

    def test_build_explanation_clinical_summary(self):
        """Should build explanation for clinical summary."""
        result = {
            "risk_level": "LOW",
            "summary": "Paciente apresenta melhora do quadro.",
            "key_points": ["Ponto 1"],
        }
        explanation = _build_explanation("CLINICAL_SUMMARY", result, "gpt-4o-mini")
        assert "Resumo clínico" in explanation["text"]

    def test_build_explanation_cached_flag(self):
        """Should set cached flag correctly."""
        result = {"risk_level": "LOW"}
        explanation = _build_explanation("DRUG_INTERACTION_CHECK", result, "gpt-4o-mini", cached=True)
        assert explanation["cached"] is True

    def test_build_explanation_unknown_risk(self):
        """Should handle unknown risk level."""
        result = {"risk_level": "UNKNOWN"}
        explanation = _build_explanation("DRUG_INTERACTION_CHECK", result, "gpt-4o-mini")
        assert "Não foi possível determinar" in explanation["text"]


# ─── Cache ───────────────────────────────────────────────────────────────────

class TestAnalysisCache:
    async def test_cache_hit_returns_cached_result(self, ai_service, mock_db, mock_redis):
        """Should return cached result and mark job as cached."""
        job_id = str(uuid.uuid4())
        cached_result = {"risk_level": "LOW", "interactions_found": []}

        mock_db.analysis_jobs.find_one.return_value = {
            "_id": job_id,
            "analysis_type": "DRUG_INTERACTION_CHECK",
            "patient_id": "pat_123",
            "context": {"medications": [{"name": "Dipirona"}]},
            "status": "PENDING",
        }
        mock_db.analysis_jobs.update_one = AsyncMock()

        # Simulate cache hit
        cache_key = _compute_cache_key("DRUG_INTERACTION_CHECK", {"medications": [{"name": "Dipirona"}]})
        mock_redis.get.return_value = json.dumps(cached_result)

        result = await ai_service.run_analysis(job_id)
        assert result["cached"] is True
        assert result["result"] == cached_result
        assert result["status"] == "COMPLETED"
        assert result["explanation"] is not None
        assert result["explanation"]["cached"] is True

    async def test_cache_miss_calls_dispatch(self, ai_service, mock_db, mock_redis):
        """Should call dispatch on cache miss and store result."""
        job_id = str(uuid.uuid4())
        mock_db.analysis_jobs.find_one.return_value = {
            "_id": job_id,
            "analysis_type": "DRUG_INTERACTION_CHECK",
            "patient_id": "pat_123",
            "context": {"medications": [{"name": "Dipirona"}]},
            "status": "PENDING",
        }
        mock_db.analysis_jobs.update_one = AsyncMock()
        mock_redis.get.return_value = None  # cache miss

        with patch.object(ai_service, "_dispatch") as mock_dispatch:
            mock_dispatch.return_value = {
                "risk_level": "LOW",
                "interactions_found": [],
                "allergy_conflicts": [],
                "recommendations": [],
            }
            result = await ai_service.run_analysis(job_id)
            assert result["cached"] is False
            assert result["status"] == "COMPLETED"
            mock_dispatch.assert_called_once()

    async def test_cache_disabled(self, ai_service, mock_db, mock_redis):
        """Should skip cache when CACHE_ENABLED is False."""
        with patch.object(settings, "CACHE_ENABLED", False):
            job_id = str(uuid.uuid4())
            mock_db.analysis_jobs.find_one.return_value = {
                "_id": job_id,
                "analysis_type": "DRUG_INTERACTION_CHECK",
                "patient_id": "pat_123",
                "context": {},
                "status": "PENDING",
            }
            mock_db.analysis_jobs.update_one = AsyncMock()

            with patch.object(ai_service, "_dispatch") as mock_dispatch:
                mock_dispatch.return_value = {"risk_level": "LOW", "interactions_found": []}
                await ai_service.run_analysis(job_id)
                # Should NOT have checked cache
                mock_redis.get.assert_not_called()


# ─── Timeout ─────────────────────────────────────────────────────────────────

class TestAnalysisTimeout:
    async def test_timeout_sets_job_to_failed(self, ai_service, mock_db):
        """Should set job to FAILED on timeout."""
        job_id = str(uuid.uuid4())
        mock_db.analysis_jobs.find_one.return_value = {
            "_id": job_id,
            "analysis_type": "DRUG_INTERACTION_CHECK",
            "patient_id": "pat_123",
            "context": {},
            "status": "PENDING",
        }
        mock_db.analysis_jobs.update_one = AsyncMock()

        with patch.object(ai_service, "_dispatch") as mock_dispatch:
            mock_dispatch.side_effect = TimeoutError("Timed out")

            with pytest.raises(TimeoutError):
                await ai_service.run_analysis(job_id)

            # Verify job was marked as FAILED
            update_call = mock_db.analysis_jobs.update_one.call_args
            assert update_call is not None
            set_values = update_call[0][1]["$set"]
            assert set_values["status"] == "FAILED"
            assert "Timed out" in set_values["error_message"]


# ─── Mock Fallback ───────────────────────────────────────────────────────────

class TestMockFallback:
    async def test_mock_response_when_no_api_key(self, ai_service):
        """Should return mock response when no API key is configured."""
        with patch.object(settings, "LLM_API_KEY", ""):
            result = await ai_service._check_drug_interactions({"medications": []})
            assert "disclaimer" in result
            assert "simulada" in result["disclaimer"]

    async def test_mock_response_on_llm_failure(self, ai_service):
        """Should fall back to mock when LLM call fails."""
        with patch.object(ai_service, "_get_llm_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.call.side_effect = Exception("API error")
            mock_get_client.return_value = mock_client

            result = await ai_service._call_llm("prompt", "drug_interaction")
            assert "disclaimer" in result
            assert "simulada" in result["disclaimer"]

    async def test_mock_response_on_validation_failure(self, ai_service):
        """Should fall back to mock when LLM response validation fails."""
        from app.infrastructure.llm_client import LLMResponseValidationError

        with patch.object(ai_service, "_get_llm_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.call.side_effect = LLMResponseValidationError("Invalid response")
            mock_get_client.return_value = mock_client

            result = await ai_service._call_llm("prompt", "drug_interaction")
            assert "disclaimer" in result
            assert "simulada" in result["disclaimer"]


# ─── Job Lifecycle ───────────────────────────────────────────────────────────

class TestJobLifecycle:
    async def test_create_job(self, ai_service, mock_db):
        """Should create a job with correct initial state."""
        mock_db.analysis_jobs.insert_one = AsyncMock()

        job = await ai_service.create_job(
            analysis_type="DRUG_INTERACTION_CHECK",
            patient_id="pat_123",
            record_id="rec_456",
            context={"medications": []},
        )

        assert job["status"] == "PENDING"
        assert job["analysis_type"] == "DRUG_INTERACTION_CHECK"
        assert job["patient_id"] == "pat_123"
        assert job["record_id"] == "rec_456"
        assert job["result"] is None
        assert job["risk_level"] is None
        assert job["explanation"] is None
        assert job["attempts"] == 0
        assert job["latency_seconds"] is None
        assert job["cached"] is False
        assert job["error_message"] is None
        assert job["model_version"] == settings.LLM_MODEL

    async def test_run_analysis_success(self, ai_service, mock_db):
        """Should run analysis and update job to COMPLETED."""
        job_id = str(uuid.uuid4())
        mock_db.analysis_jobs.find_one.return_value = {
            "_id": job_id,
            "analysis_type": "DRUG_INTERACTION_CHECK",
            "patient_id": "pat_123",
            "context": {"medications": [{"name": "Dipirona"}]},
            "status": "PENDING",
        }
        mock_db.analysis_jobs.update_one = AsyncMock()

        with patch.object(ai_service, "_dispatch") as mock_dispatch:
            mock_dispatch.return_value = {
                "risk_level": "LOW",
                "interactions_found": [],
                "allergy_conflicts": [],
                "recommendations": ["Monitorar"],
            }
            result = await ai_service.run_analysis(job_id)

            assert result["status"] == "COMPLETED"
            assert result["risk_level"] == "LOW"
            assert result["latency_seconds"] is not None
            assert result["explanation"] is not None

    async def test_run_analysis_failure(self, ai_service, mock_db):
        """Should set job to FAILED on analysis error."""
        job_id = str(uuid.uuid4())
        mock_db.analysis_jobs.find_one.return_value = {
            "_id": job_id,
            "analysis_type": "DRUG_INTERACTION_CHECK",
            "patient_id": "pat_123",
            "context": {},
            "status": "PENDING",
        }
        mock_db.analysis_jobs.update_one = AsyncMock()

        with patch.object(ai_service, "_dispatch") as mock_dispatch:
            mock_dispatch.side_effect = ValueError("Analysis error")

            with pytest.raises(ValueError):
                await ai_service.run_analysis(job_id)

            # Verify FAILED status
            update_call = mock_db.analysis_jobs.update_one.call_args
            set_values = update_call[0][1]["$set"]
            assert set_values["status"] == "FAILED"
            assert "Analysis error" in set_values["error_message"]

    async def test_get_job(self, ai_service, mock_db):
        """Should retrieve a job by ID."""
        job_id = str(uuid.uuid4())
        mock_db.analysis_jobs.find_one.return_value = {"_id": job_id, "status": "COMPLETED"}

        job = await ai_service.get_job(job_id)
        assert job["_id"] == job_id
        assert job["status"] == "COMPLETED"

    async def test_get_job_not_found(self, ai_service, mock_db):
        """Should return None for non-existent job."""
        mock_db.analysis_jobs.find_one.return_value = None
        job = await ai_service.get_job("nonexistent")
        assert job is None

    async def test_list_by_record(self, ai_service, mock_db):
        """Should list analyses for a record."""
        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=[
            {"_id": "1", "record_id": "rec_123"},
            {"_id": "2", "record_id": "rec_123"},
        ])
        mock_db.analysis_jobs.find.return_value = mock_cursor

        jobs = await ai_service.list_by_record("rec_123")
        assert len(jobs) == 2
        mock_db.analysis_jobs.find.assert_called_once_with({"record_id": "rec_123"})


# ─── Cache Key ───────────────────────────────────────────────────────────────

class TestCacheKey:
    def test_cache_key_deterministic(self):
        """Should produce same key for same input."""
        key1 = _compute_cache_key("DRUG_INTERACTION_CHECK", {"meds": ["A"]})
        key2 = _compute_cache_key("DRUG_INTERACTION_CHECK", {"meds": ["A"]})
        assert key1 == key2

    def test_cache_key_different_for_different_input(self):
        """Should produce different keys for different inputs."""
        key1 = _compute_cache_key("DRUG_INTERACTION_CHECK", {"meds": ["A"]})
        key2 = _compute_cache_key("DRUG_INTERACTION_CHECK", {"meds": ["B"]})
        assert key1 != key2

    def test_cache_key_different_for_different_types(self):
        """Should produce different keys for different analysis types."""
        key1 = _compute_cache_key("DRUG_INTERACTION_CHECK", {})
        key2 = _compute_cache_key("SYMPTOM_ANALYSIS", {})
        assert key1 != key2