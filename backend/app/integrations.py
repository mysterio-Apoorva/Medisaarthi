"""Interoperability adapters. Development adapters are local mappers, not claimed live integrations."""

from __future__ import annotations

from typing import Any


def fhir_patient(patient: dict[str, Any]) -> dict[str, Any]:
    return {"resourceType": "Patient", "id": patient["patient_id"], "name": [{"text": patient["name"]}], "gender": patient["gender"].casefold(), "extension": [{"url": "https://medikiosk.local/fhir/synthetic", "valueBoolean": "Synthetic" in patient["name"]}]}


def fhir_encounter(encounter: dict[str, Any]) -> dict[str, Any]:
    return {"resourceType": "Encounter", "id": encounter["encounter_id"], "status": encounter["status"].casefold(), "subject": {"reference": f"Patient/{encounter['patient_id']}"}, "period": {"start": encounter["started_at"], "end": encounter.get("completed_at")}}


def fhir_observation(patient_id: str, fact: dict[str, Any]) -> dict[str, Any]:
    return {"resourceType": "Observation", "status": "preliminary" if fact["status"] != "VERIFIED" else "final", "subject": {"reference": f"Patient/{patient_id}"}, "code": {"text": fact["field_name"]}, "valueString": str(fact["value"]), "note": [{"text": f"Provenance: {fact['source']}"}]}


class DevelopmentABDMAdapter:
    """Offline-only contract adapter. It performs no ABDM network call."""
    mode = "development_adapter"

    def create_consent_artifact(self, consent: dict[str, Any]) -> dict[str, Any]:
        return {"mode": self.mode, "resourceType": "Consent", "identifier": consent["consent_id"], "status": consent["status"], "purpose": consent["purpose"]}


class DevelopmentHISAdapter:
    """A local interchange shape for HIS demos; live HIS connectivity requires configured credentials."""
    mode = "development_adapter"

    def patient_lookup(self, patient: dict[str, Any]) -> dict[str, Any]:
        return {"mode": self.mode, "patient": fhir_patient(patient)}
