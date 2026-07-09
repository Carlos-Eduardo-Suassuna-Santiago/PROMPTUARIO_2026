"""
Pydantic schemas for LLM response validation.
Each analysis type has an explicit schema that the LLM response must conform to.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


# ─── Drug Interaction ─────────────────────────────────────────────────────────

class InteractionFound(BaseModel):
    drugs: list[str] = Field(min_length=2)
    severity: str = Field(pattern=r"^(LOW|MEDIUM|HIGH|CRITICAL)$")
    description: str = Field(min_length=5, max_length=1000)


class AllergyConflict(BaseModel):
    medication: str = Field(min_length=1)
    allergen: str = Field(min_length=1)
    risk: str = Field(pattern=r"^(LOW|MEDIUM|HIGH|CRITICAL)$")


class DrugInteractionResponse(BaseModel):
    risk_level: str = Field(pattern=r"^(LOW|MEDIUM|HIGH|CRITICAL|UNKNOWN)$")
    interactions_found: list[InteractionFound] = []
    allergy_conflicts: list[AllergyConflict] = []
    recommendations: list[str] = []
    disclaimer: str = Field(default="Ferramenta de apoio — decisão final é do médico", max_length=500)


# ─── Symptom Analysis ─────────────────────────────────────────────────────────

class SymptomAnalysisResponse(BaseModel):
    risk_level: str = Field(pattern=r"^(LOW|MEDIUM|HIGH|CRITICAL|UNKNOWN)$")
    possible_diagnoses: list[str] = Field(default_factory=list)
    recommended_exams: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    disclaimer: str = Field(default="Ferramenta de apoio — decisão final é do médico", max_length=500)


# ─── Clinical Summary ─────────────────────────────────────────────────────────

class ClinicalSummaryResponse(BaseModel):
    risk_level: str = Field(pattern=r"^(LOW|MEDIUM|HIGH|UNKNOWN)$")
    summary: str = Field(min_length=10, max_length=5000)
    key_points: list[str] = Field(default_factory=list)
    disclaimer: str = Field(default="Ferramenta de apoio — decisão final é do médico", max_length=500)


# ─── Response Validator ───────────────────────────────────────────────────────

RESPONSE_SCHEMA_MAP = {
    "drug_interaction": DrugInteractionResponse,
    "symptom_analysis": SymptomAnalysisResponse,
    "clinical_summary": ClinicalSummaryResponse,
}


def validate_llm_response(raw: dict, schema_name: str) -> dict:
    """
    Validate that a raw LLM response conforms to the expected schema.
    
    Args:
        raw: Raw dictionary from LLM.
        schema_name: One of 'drug_interaction', 'symptom_analysis', 'clinical_summary'.
    
    Returns:
        Validated and cleaned dictionary.
    
    Raises:
        ValueError: If validation fails with details about what is invalid.
    """
    schema_class = RESPONSE_SCHEMA_MAP.get(schema_name)
    if not schema_class:
        raise ValueError(f"Unknown response schema: {schema_name}")

    try:
        validated = schema_class(**raw)
        return validated.model_dump()
    except Exception as e:
        raise ValueError(f"LLM response validation failed for '{schema_name}': {e}. Raw: {raw}")