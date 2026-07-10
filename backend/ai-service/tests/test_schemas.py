"""
Tests for LLM response schema validation.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.schemas import (
    DrugInteractionResponse,
    SymptomAnalysisResponse,
    ClinicalSummaryResponse,
    validate_llm_response,
)


class TestDrugInteractionSchema:
    def test_valid_response(self):
        """Should accept a valid drug interaction response."""
        data = {
            "risk_level": "HIGH",
            "interactions_found": [
                {
                    "drugs": ["Losartana", "Ibuprofeno"],
                    "severity": "HIGH",
                    "description": "Aumento do risco de insuficiência renal",
                }
            ],
            "allergy_conflicts": [
                {
                    "medication": "Amoxicilina",
                    "allergen": "Penicilina",
                    "risk": "CRITICAL",
                }
            ],
            "recommendations": ["Suspender Ibuprofeno", "Monitorar creatinina"],
            "disclaimer": "Ferramenta de apoio — decisão final é do médico",
        }
        validated = DrugInteractionResponse(**data)
        assert validated.risk_level == "HIGH"
        assert len(validated.interactions_found) == 1
        assert len(validated.recommendations) == 2

    def test_invalid_risk_level(self):
        """Should reject invalid risk level."""
        with pytest.raises(ValidationError) as exc:
            DrugInteractionResponse(
                risk_level="INVALID",
                interactions_found=[],
                allergy_conflicts=[],
                recommendations=[],
            )
        assert "risk_level" in str(exc.value)

    def test_missing_required_fields(self):
        """Should require all mandatory fields."""
        with pytest.raises(ValidationError):
            DrugInteractionResponse()

    def test_empty_lists_allowed(self):
        """Should accept empty lists for interactions and conflicts."""
        data = {
            "risk_level": "LOW",
            "interactions_found": [],
            "allergy_conflicts": [],
            "recommendations": [],
        }
        validated = DrugInteractionResponse(**data)
        assert validated.interactions_found == []
        assert validated.allergy_conflicts == []


class TestSymptomAnalysisSchema:
    def test_valid_response(self):
        """Should accept a valid symptom analysis response."""
        data = {
            "risk_level": "MEDIUM",
            "possible_diagnoses": ["Enxaqueca", "Cefaleia tensional"],
            "recommended_exams": ["TC de crânio"],
            "red_flags": ["Piora progressiva"],
            "disclaimer": "Ferramenta de apoio",
        }
        validated = SymptomAnalysisResponse(**data)
        assert validated.risk_level == "MEDIUM"
        assert len(validated.possible_diagnoses) == 2

    def test_invalid_risk_level(self):
        """Should reject invalid risk level."""
        with pytest.raises(ValidationError):
            SymptomAnalysisResponse(
                risk_level="INVALID",
                possible_diagnoses=[],
                recommended_exams=[],
                red_flags=[],
            )


class TestClinicalSummarySchema:
    def test_valid_response(self):
        """Should accept a valid clinical summary response."""
        data = {
            "risk_level": "LOW",
            "summary": "Paciente apresenta quadro de enxaqueca sem aura, com boa resposta ao tratamento.",
            "key_points": ["Diagnóstico: Enxaqueca", "Tratamento: Analgésicos"],
            "disclaimer": "Ferramenta de apoio",
        }
        validated = ClinicalSummaryResponse(**data)
        assert validated.risk_level == "LOW"
        assert len(validated.key_points) == 2

    def test_summary_too_short(self):
        """Should reject summary shorter than 10 chars."""
        with pytest.raises(ValidationError):
            ClinicalSummaryResponse(
                risk_level="LOW",
                summary="Curto",
                key_points=[],
            )


class TestValidateLLMResponse:
    def test_validates_drug_interaction(self):
        """Should validate and return cleaned dict."""
        raw = {
            "risk_level": "HIGH",
            "interactions_found": [
                {"drugs": ["A", "B"], "severity": "HIGH", "description": "Descrição da interação"}
            ],
            "allergy_conflicts": [],
            "recommendations": ["Recomendação 1"],
            "disclaimer": "Teste",
        }
        result = validate_llm_response(raw, "drug_interaction")
        assert result["risk_level"] == "HIGH"
        assert len(result["interactions_found"]) == 1

    def test_rejects_invalid(self):
        """Should raise ValueError for invalid response."""
        raw = {"risk_level": "INVALID"}
        with pytest.raises(ValueError) as exc:
            validate_llm_response(raw, "drug_interaction")
        assert "validation failed" in str(exc.value).lower()

    def test_unknown_schema(self):
        """Should raise ValueError for unknown schema."""
        with pytest.raises(ValueError) as exc:
            validate_llm_response({}, "unknown_schema")
        assert "unknown" in str(exc.value).lower()