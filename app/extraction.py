"""Validate provider evidence before touching interview state."""

from app.interview.schemas import ClinicalState, Extraction
from app.llm.client import ProviderError

HISTORY_FIELDS = frozenset(
    {"past_medical_history", "medications", "allergies", "family_history", "personal_history"}
)


def apply_extraction(state: ClinicalState, extraction: Extraction, statement: str) -> ClinicalState:
    updated = state.model_dump()
    complaint = next((fact for fact in extraction.facts if fact.field == "chief_complaint"), None)
    if (
        complaint is not None
        and complaint.value != state.chief_complaint
        and state.chief_complaint is not None
    ):
        # A replacement complaint must not inherit another complaint's duration/severity.
        updated = ClinicalState(**{field: updated[field] for field in HISTORY_FIELDS}).model_dump()
    for fact in extraction.facts:
        if fact.evidence not in statement:
            raise ProviderError("Extraction evidence is not present in the patient statement")
        updated[fact.field] = fact.value
    return ClinicalState.model_validate(updated)
