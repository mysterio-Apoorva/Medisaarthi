"""Tests for the active FastAPI, SQLite, clinical-engine architecture.

Each test run receives an isolated synthetic SQLite database.  These tests
never use a mock STT response or a caller-supplied doctor identity; the
separate voice smoke test exercises a real local faster-whisper model using a
caller-provided spoken recording.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


_test_directory = Path(tempfile.mkdtemp(prefix="medikiosk-pytest-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_test_directory / 'medikiosk.sqlite3'}"
os.environ["AI_PROVIDER"] = "clinical_rules"

from backend.app.ai.providers import AIProvider
from backend.app.clinical_engine import completeness, red_flags
from backend.app.main import app


def _expect(response, status_code: int):
    assert response.status_code == status_code, response.text
    return response.json() if response.content else None


def _patient_session(client: TestClient) -> None:
    _expect(
        client.post(
            "/auth/login",
            json={"email": "patient.demo@medikiosk.local", "password": "DemoPass!2026"},
        ),
        200,
    )


def _new_encounter(client: TestClient) -> dict:
    _patient_session(client)
    consent = _expect(
        client.post(
            "/interviews/consents",
            json={"patient_id": "P1001", "consent_type": "CLINICAL_INTAKE"},
        ),
        201,
    )
    return _expect(
        client.post(
            "/interviews/start",
            json={"patient_id": "P1001", "language": "en", "consent_id": consent["consent_id"]},
        ),
        201,
    )


def test_api_enforces_authenticated_patient_boundary() -> None:
    with TestClient(app) as client:
        _expect(client.get("/patients/P1001"), 401)
        _patient_session(client)
        _expect(client.get("/patients/P1001"), 200)
        _expect(client.get("/patients/P1002"), 403)


def test_intake_updates_state_revision_and_deterministic_red_flags() -> None:
    with TestClient(app) as client:
        started = _new_encounter(client)
        encounter_id = started["encounter_id"]
        first = _expect(
            client.post(
                f"/interviews/{encounter_id}/answers",
                json={"message": "I have chest pain since yesterday.", "expected_revision": started["revision"]},
            ),
            200,
        )
        assert first["clinical_state"]["chief_complaint"] == "chest pain"
        assert first["clinical_state"]["duration"] == "since yesterday"
        _expect(
            client.post(
                f"/interviews/{encounter_id}/answers",
                json={"message": "this stale answer must not be stored", "expected_revision": started["revision"]},
            ),
            409,
        )
        assert first["next_question"]["id"] == "breathlessness"

        second = _expect(
            client.post(
                f"/interviews/{encounter_id}/answers",
                json={"message": "It is 8 out of 10 and I am short of breath.", "expected_revision": first["revision"]},
            ),
            200,
        )
        assert second["clinical_state"]["severity"] == 8
        assert second["clinical_state"]["breathlessness"] is True
        assert any(flag["code"] == "CHEST_PAIN_BREATHLESSNESS" for flag in second["priority_flags"])


def test_voice_endpoint_rejects_invalid_media_before_transcription() -> None:
    with TestClient(app) as client:
        started = _new_encounter(client)
        response = client.post(
            f"/interviews/{started['encounter_id']}/voice",
            data={"expected_revision": str(started["revision"])},
            files={"file": ("not-a-recording.wav", b"not a RIFF file", "audio/wav")},
        )
        _expect(response, 415)


def test_model_suggestion_cannot_replace_rule_validated_current_question() -> None:
    class UnsafeModel(AIProvider):
        name = "unsafe-test-model"

        def generate(self, prompt: str) -> str:
            return json.dumps(
                {
                    "facts": [
                        {
                            "field_name": "chest_pain",
                            "value": "since yesterday",
                            "evidence": "I have chest pain since yesterday.",
                            "confidence": 1.0,
                        }
                    ]
                }
            )

    extraction = UnsafeModel().extract("I have chest pain since yesterday.", "chief_complaint", {})
    facts = {fact.field_name: fact.value for fact in extraction.facts}
    assert facts["chief_complaint"] == "chest pain"
    assert facts["duration"] == "since yesterday"
    assert "chest_pain" not in facts


def test_clinical_rules_do_not_diagnose_and_report_missing_information() -> None:
    state = {"chief_complaint": "chest pain", "duration": "since yesterday", "severity": 8, "breathlessness": True}
    quality = completeness(state)
    assert "location" in quality["missing"]
    assert "chest_pain" not in state
    flags = red_flags(state)
    assert flags == [
        {
            "code": "CHEST_PAIN_BREATHLESSNESS",
            "severity": "EMERGENCY",
            "message": "Chest discomfort with breathing difficulty needs immediate clinician assessment.",
            "evidence": ["chief_complaint", "breathlessness"],
        }
    ]


def test_doctor_session_can_review_only_assigned_patient() -> None:
    with TestClient(app) as client:
        registration = _expect(
            client.post(
                "/auth/register",
                json={
                    "name": "Unassigned Synthetic Patient",
                    "age": 31,
                    "gender": "Other",
                    "language": "en",
                    "email": "unassigned.patient@medikiosk.test",
                    "password": "SyntheticPass!2026",
                },
            ),
            201,
        )
        _expect(client.post("/auth/logout"), 204)
        _expect(
            client.post(
                "/auth/login",
                json={"email": "doctor.demo@medikiosk.local", "password": "DemoPass!2026"},
            ),
            200,
        )
        queue = _expect(client.get("/doctor/patients"), 200)
        assert any(patient["patient_id"] == "P1001" for patient in queue)
        _expect(client.get(f"/doctor/patients/{registration['patient_id']}/summary"), 403)
