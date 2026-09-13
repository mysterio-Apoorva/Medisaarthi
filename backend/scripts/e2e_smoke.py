"""Runnable local end-to-end proof for the synthetic MediKiosk demonstration."""

from __future__ import annotations

import tempfile
import io
import wave
from pathlib import Path
import sys

import pymupdf
from fastapi.testclient import TestClient

# Script execution sets sys.path to backend/scripts; make repository imports explicit.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.main import app


def expect(response, code: int):
    assert response.status_code == code, response.text
    return response.json() if response.content else None


def silent_wav() -> bytes:
    """A valid WAV with no speech; STT must reject it rather than invent text."""
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 16000)
    return output.getvalue()


def main() -> None:
    with TestClient(app) as client:
        expect(client.get("/health"), 200)
        expect(client.post("/auth/login", json={"email": "patient.demo@medikiosk.local", "password": "DemoPass!2026"}), 200)
        # RBAC / IDOR boundary: this account belongs only to P1001.
        expect(client.get("/patients/P1002"), 403)

        clinical_consent = expect(client.post("/interviews/consents", json={"patient_id": "P1001", "consent_type": "CLINICAL_INTAKE"}), 201)
        expect(client.post("/interviews/consents", json={"patient_id": "P1001", "consent_type": "DOCUMENT_PROCESSING"}), 201)
        started = expect(client.post("/interviews/start", json={"patient_id": "P1001", "language": "en", "consent_id": clinical_consent["consent_id"]}), 201)
        encounter_id, revision = started["encounter_id"], started["revision"]
        # Real local STT safety check: silence is not converted into a fabricated answer.
        silence = client.post(
            f"/interviews/{encounter_id}/voice",
            data={"expected_revision": str(revision)},
            files={"file": ("silence.wav", silent_wav(), "audio/wav")},
        )
        expect(silence, 422)

        answers = {
            "chief_complaint": "I have chest pain since yesterday.", "onset": "It started yesterday", "duration": "since yesterday", "location": "central chest", "severity": "8 out of 10", "character": "heavy pressure", "radiation": "It does not move anywhere", "exertion": "It gets worse when walking", "breathlessness": "yes, I am short of breath", "sweating": "yes, sweating", "nausea": "no nausea", "frequency": "twice today", "vomiting": "no", "abdominal_pain": "no", "chest_pain": "yes", "cough": "no", "fever": "no", "sudden_onset": "no", "fainting": "no", "past_medical_history": "hypertension", "medications": "amlodipine 5 mg", "allergies": "no known allergies",
        }
        turn = started
        answers.update({'past_surgical_history':'none','family_history':'Father has hypertension','social_history':'I do not smoke. I am a teacher.','personal_history':'Sleep has been disturbed','review_of_systems':'none'})
        for _ in range(30):
            question = turn.get("next_question")
            if not question:
                break
            field = question["id"]
            assert field in answers, f"No answer for required field {field}"
            turn = expect(client.post(f"/interviews/{encounter_id}/answers", json={"message": answers[field], "expected_revision": revision}), 200)
            revision = turn["revision"]
        assert turn["completion"]["critical_missing"] == [], turn
        assert any(flag["code"] == "CHEST_PAIN_BREATHLESSNESS" for flag in turn["priority_flags"]), turn

        # Actual PDF generation + upload + local extraction; document values remain pending clinician reconciliation.
        with tempfile.NamedTemporaryFile(suffix=".pdf") as temp:
            pdf = pymupdf.open(); page = pdf.new_page(); page.insert_text((72, 72), "Patient report\nTablet Aspirin 75 mg\nAllergies: none known"); pdf.save(temp.name); pdf.close()
            uploaded = expect(client.post(f"/documents/encounters/{encounter_id}", files={"file": ("synthetic-report.pdf", Path(temp.name).read_bytes(), "application/pdf")}), 201)
            assert uploaded["processing_status"] == "PROCESSED", uploaded

        expect(client.post(f"/interviews/{encounter_id}/submit", json={"expected_revision": revision, "reviewed": True}), 200)
        expect(client.post("/auth/login", json={"email": "doctor.demo@medikiosk.local", "password": "DemoPass!2026"}), 200)
        summary = expect(client.get("/doctor/patients/P1001/summary"), 200)
        assert summary["encounter"]["encounter_id"] == encounter_id
        assert summary["red_flags"], summary
        assert summary["reconciliation"], summary
        for item in summary["reconciliation"]:
            expect(client.post(f"/doctor/reconciliation/{item['reconciliation_id']}", json={"action": "APPROVED"}), 200)
        expect(client.post("/doctor/patients/P1001/facts", json={"field_name": "severity", "value": 7, "reason": "Clinician confirmed severity after review"}), 200)
        expect(client.post(f"/doctor/encounters/{encounter_id}/finalize"), 200)
        expect(client.post("/auth/login", json={"email": "admin.demo@medikiosk.local", "password": "DemoPass!2026"}), 200)
        audits = expect(client.get("/admin/audit-logs"), 200)
        assert any(item["action"] == "ENCOUNTER_FINALIZED" for item in audits)
        users = expect(client.get("/admin/users"), 200)
        assert any(item["role"] == "ADMIN" for item in users)
        saved_rule = expect(client.put("/admin/ontology/RULE_E2E_SMOKE", json={"concept": "e2e smoke", "payload": {"synonyms": ["test-only"], "required": []}, "enabled": True}), 200)
        assert saved_rule["rule_id"] == "RULE_E2E_SMOKE"
    print("E2E smoke passed: patient intake -> rules/AI fallback -> document reconciliation -> doctor finalization -> audit")


if __name__ == "__main__":
    main()
