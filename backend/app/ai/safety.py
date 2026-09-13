"""One illustrative flag from the project specification, owned clinically by M4."""

from app.ai.interview.schemas import ClinicalState, PriorityFlag


def priority_flags(state: ClinicalState) -> list[PriorityFlag]:
    if state.chief_complaint == "chest pain" and state.breathlessness is True:
        return [
            PriorityFlag(
                code="CHEST_PAIN_WITH_BREATHLESSNESS",
                message="Patient reports chest pain with breathing difficulty. Alert hospital staff for prompt review.",
                evidence_fields=["chief_complaint", "breathlessness"],
            )
        ]
    return []
