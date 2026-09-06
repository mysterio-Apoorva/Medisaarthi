from fastapi.testclient import TestClient

from app.api.main import create_app
from app.config import Settings, build_service
from app.llm.mock import MockProvider
from app.persistence import SQLiteRepository


def integrated_client(tmp_path):
    repository = SQLiteRepository(tmp_path / "medisaarthi.db")
    service = build_service(Settings(), provider=MockProvider(), store=repository)
    return TestClient(create_app(service, repository)), repository


def test_durable_patient_to_doctor_workflow(tmp_path):
    api, repository = integrated_client(tmp_path)
    with api:
        assert api.get("/auth/status").json() == {"needs_setup": True}
        setup = api.post(
            "/auth/setup",
            json={"username": "doctor.one", "display_name": "Dr One", "password": "strong-pass-1"},
        )
        assert setup.status_code == 201
        token = setup.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert api.get("/doctor/patients").status_code == 401

        started = api.post(
            "/interview/start",
            json={
                "patient": {
                    "patient_id": "P9001",
                    "name": "Integration Patient",
                    "age": 48,
                    "gender": "male",
                    "language": "en",
                },
                "consent": True,
            },
        )
        assert started.status_code == 201
        interview_id = started.json()["interview_id"]

        history = api.put(
            "/patients/P9001/history",
            json={
                "conditions": [{"name": "Hypertension", "since": "2021"}],
                "medications": [{"name": "Amlodipine", "dosage": "5 mg"}],
                "allergies": [{"name": "Penicillin", "reaction": "rash"}],
            },
            headers=headers,
        )
        assert history.status_code == 200

        response = api.post(
            "/interview/respond",
            json={
                "interview_id": interview_id,
                "response": "Chest pain for 3 days, 7/10, with breathlessness",
                "expected_revision": 0,
            },
        )
        assert response.status_code == 200
        completed = api.post(
            "/interview/complete",
            json={"interview_id": interview_id, "expected_revision": 1},
        )
        assert completed.status_code == 200 and completed.json()["completed"]

        queue = api.get("/doctor/patients", headers=headers).json()
        assert queue[0]["chief_complaint"] == "chest pain"
        summary_response = api.get(
            f"/doctor/patients/P9001/summary?interview_id={interview_id}", headers=headers
        )
        assert summary_response.status_code == 200
        summary = summary_response.json()
        assert summary["past_history"] == ["Hypertension since 2021"]
        assert summary["medications"] == ["Amlodipine 5 mg"]
        assert summary["allergies"] == ["Penicillin — rash"]
        assert summary["priority_flags"]

        editable = {
            key: summary[key]
            for key in (
                "patient_snapshot",
                "current_complaint",
                "interview_summary",
                "past_history",
                "medications",
                "allergies",
                "important_findings",
                "missing_information",
                "priority_flags",
            )
        }
        editable["interview_summary"] += " Verified against the patient statement."
        saved = api.put(
            f"/doctor/interviews/{interview_id}/summary",
            json={"summary": editable, "expected_version": summary["version"]},
            headers=headers,
        )
        assert saved.status_code == 200
        approved = api.post(
            f"/doctor/interviews/{interview_id}/approve",
            json={"expected_version": saved.json()["version"]},
            headers=headers,
        )
        assert approved.status_code == 200 and approved.json()["status"] == "approved"

        timeline = api.get("/doctor/patients/P9001/timeline", headers=headers).json()
        assert {event["source"] for event in timeline} == {
            "patient_record",
            "patient_interview",
        }

    reopened = SQLiteRepository(repository.path)
    assert reopened.get(interview_id).completed
    assert reopened.get_summary(interview_id)["status"] == "approved"


def test_first_doctor_setup_is_one_time_and_login_is_real(tmp_path):
    api, _ = integrated_client(tmp_path)
    with api:
        body = {"username": "doctor", "display_name": "Doctor", "password": "password-123"}
        assert api.post("/auth/setup", json=body).status_code == 201
        assert api.post("/auth/setup", json=body).status_code == 409
        assert (
            api.post(
                "/auth/login", json={"username": "doctor", "password": "wrong-pass"}
            ).status_code
            == 401
        )
        assert (
            api.post(
                "/auth/login", json={"username": "doctor", "password": "password-123"}
            ).status_code
            == 200
        )
