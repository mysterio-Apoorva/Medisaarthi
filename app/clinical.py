"""Physician-facing synthesis from validated interview and history data."""

from typing import Any

from app.interview.engine import InterviewEngine
from app.interview.schemas import Interview


def _medication_text(item: dict[str, Any]) -> str:
    return " ".join(
        part for part in (item["name"], item.get("dosage"), item.get("frequency")) if part
    )


def _condition_text(item: dict[str, Any]) -> str:
    return f"{item['name']} since {item['since']}" if item.get("since") else item["name"]


def _allergy_text(item: dict[str, Any]) -> str:
    return f"{item['name']} — {item['reaction']}" if item.get("reaction") else item["name"]


def _merge_unique(stored: list[str], reported: list[str] | None) -> list[str]:
    result = list(stored)
    seen = {item.casefold() for item in result}
    for item in reported or []:
        if item.casefold() not in seen:
            result.append(f"{item} (patient reported in current interview)")
            seen.add(item.casefold())
    return result


def build_clinical_summary(
    patient: dict[str, Any],
    interview: Interview,
    history: dict[str, Any],
    engine: InterviewEngine,
) -> dict[str, Any]:
    """Build a conservative summary without diagnosing or inventing missing facts."""

    state = interview.clinical_state
    phrases: list[str] = []
    if state.chief_complaint:
        phrase = f"Patient reports {state.chief_complaint}"
        if state.duration:
            phrase += f" for {state.duration}"
        if state.severity is not None:
            phrase += f", severity {state.severity}/10"
        phrases.append(phrase + ".")
    if state.breathlessness is True:
        phrases.append("Patient also reports breathing difficulty.")
    elif state.breathlessness is False:
        phrases.append("Patient denies breathing difficulty.")
    if state.hpi:
        phrases.append(state.hpi.rstrip(".") + ".")
    if not phrases:
        phrases.append("The interview was completed without a reported chief complaint.")

    presentation = engine.present(interview)
    important: list[str] = []
    for field in ("temperature", "location"):
        value = getattr(state, field)
        if value:
            important.append(f"{field.replace('_', ' ').title()}: {value}")
    if state.severity is not None:
        important.append(f"Reported severity: {state.severity}/10")

    past_history = _merge_unique(
        [_condition_text(item) for item in history["conditions"]],
        state.past_medical_history,
    )
    medications = _merge_unique(
        [_medication_text(item) for item in history["medications"] if item.get("active", True)],
        state.medications,
    )
    allergies = _merge_unique(
        [_allergy_text(item) for item in history["allergies"]],
        state.allergies,
    )
    if state.medications == [] and not medications:
        medications.append("Patient reports no current medications")
    if state.allergies == [] and not allergies:
        allergies.append("Patient reports no known allergies")

    return {
        "interview_id": interview.interview_id,
        "patient_id": interview.patient_id,
        "patient_snapshot": {
            "patient_id": patient["patient_id"],
            "name": patient["name"],
            "age": patient["age"],
            "gender": patient["gender"],
            "language": patient["language"],
        },
        "current_complaint": {
            "name": state.chief_complaint,
            "duration": state.duration,
            "severity": state.severity,
        },
        "interview_summary": " ".join(phrases),
        "past_history": past_history,
        "medications": medications,
        "allergies": allergies,
        "important_findings": important,
        "missing_information": [
            field.replace("_", " ") for field in presentation.missing_information
        ],
        "priority_flags": [flag.message for flag in presentation.priority_flags],
    }
