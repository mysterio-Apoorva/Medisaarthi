from fastapi.testclient import TestClient

from app.api.main import create_app
from app.config import Settings, build_service


def client():
    return TestClient(create_app(build_service(Settings())))


def test_full_api_lifecycle():
    with client() as api:
        response = api.post(
            "/interview/start",
            json={"patient": {"patient_id": "P1001", "language": "hi"}, "consent": True},
        )
        assert response.status_code == 201
        interview_id = response.json()["interview_id"]
        body = {
            "interview_id": interview_id,
            "response": "Mujhe 3 din se fever hai.",
            "expected_revision": 0,
        }
        response = api.post("/interview/respond", json=body)
        assert response.status_code == 200
        assert response.json()["next_question"]["id"] == "temperature"
        assert api.post("/interview/respond", json=body).status_code == 409
        assert api.get(f"/interview/{interview_id}").json()["revision"] == 1
        assert len(api.get(f"/interview/{interview_id}/record").json()["responses"]) == 1
        response = api.post(
            "/interview/complete", json={"interview_id": interview_id, "expected_revision": 1}
        )
        assert response.json()["completed"]
        assert response.json()["missing_information"]


def test_input_errors_and_not_found():
    with client() as api:
        assert api.get("/interview/missing").status_code == 404
        for consent in [False, "true", 1]:
            assert (
                api.post(
                    "/interview/start",
                    json={"patient": {"patient_id": "P1001"}, "consent": consent},
                ).status_code
                == 422
            )
        assert (
            api.post(
                "/interview/start",
                json={"patient": {"patient_id": "P1001", "language": "fr"}, "consent": True},
            ).status_code
            == 422
        )


def test_app_instances_do_not_share_state():
    with client() as first, client() as second:
        record = first.post(
            "/interview/start", json={"patient": {"patient_id": "P1001"}, "consent": True}
        ).json()
        assert second.get(f"/interview/{record['interview_id']}").status_code == 404
