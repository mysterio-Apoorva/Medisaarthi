"""Integration coverage for document intelligence, AYUSH mode, and follow-up."""

from __future__ import annotations

import json
from uuid import uuid4

import pymupdf
import pytest
from fastapi.testclient import TestClient

from backend.app.clinical_engine import AYUSH_FIELDS, next_question, required_fields
from backend.app.main import app
from backend.app.routes.followups import create_follow_up_plan
from backend.app.store import now, store
from backend.tests.test_current_system import _expect, _new_encounter
from backend.app.document_processing import PageResult, _entities_from_page


@pytest.mark.parametrize('line,flag', [
    ('Hemoglobin: 11.2 g/dL (12.0-15.0)', 'LOW'),
    ('Hemoglobin: 14 g/dL (reference range: 12 - 16)', 'NORMAL'),
    ('Glucose: 168 mg/dL [normal: 70-110]', 'HIGH'),
    ('Creatinine: 1.0 mg/dL', None),
])
def test_lab_reference_range_formats(line, flag):
    entities = _entities_from_page(PageResult(1, line, 'TEXT', 1.0))
    lab = next(entity for entity in entities if entity['entity_type'] == 'INVESTIGATION')
    assert lab['abnormal_status'] == flag
    assert lab['evidence'] == line


@pytest.mark.parametrize('line,value', [('Height: 1.75 m', 'Height: 1.75 m'), ('Temperature: 98.6 F', 'Temperature: 98.6 F'), ('SpO2: 98%', 'SpO2: 98 %'), ('BP: 120/80 mmHg', 'Blood pressure: 120/80 mmHg')])
def test_document_vitals_preserve_units_and_decimal_height(line, value):
    entities = _entities_from_page(PageResult(1, line, 'TEXT', 1.0))
    vital = next(e for e in entities if e['entity_type'] == 'VITAL')
    assert vital['value'] == value and vital['evidence'] == line


def test_ayush_mode_has_structured_patient_reported_questions():
    required = required_fields({"chief_complaint": "fatigue"}, "AYUSH")
    assert set(AYUSH_FIELDS).issubset(required)
    state = {field: "reported" for field in required if field != "ahara_vihara"}
    state["chief_complaint"] = "fatigue"
    question = next_question(state, "en", "AYUSH")
    assert question and question["id"] == "ahara_vihara"
    assert question["stage"] == "AYUSH_HISTORY"


def test_document_entities_include_page_evidence_dates_and_abnormal_lab():
    with TestClient(app) as client:
        started = _new_encounter(client)
        encounter_id = started["encounter_id"]
        _expect(client.post("/interviews/consents", json={"patient_id": "P1001", "consent_type": "DOCUMENT_PROCESSING"}), 201)
        pdf = pymupdf.open()
        page = pdf.new_page()
        page.insert_text(
            (72, 72),
            "Date: 12/01/2025\nDiagnosis: Type 2 diabetes\nTablet Metformin 500 mg twice daily\nHemoglobin: 9 g/dL (reference range: 12 - 16)\nBP: 150/95 mmHg\nProcedure: Cataract surgery",
        )
        uploaded = _expect(client.post(f"/documents/encounters/{encounter_id}", files={"file": ("synthetic-lab.pdf", pdf.tobytes(), "application/pdf")}), 201)
        pdf.close()
        extracted = _expect(client.get(f"/documents/{uploaded['document_id']}/extraction"), 200)
        assert extracted["pages"] and extracted["pages"][0]["page_number"] == 1
        assert extracted["document_date"] == "2025-01-12"
        assert {entity["entity_type"] for entity in extracted["entities"]} >= {"DATE", "DIAGNOSIS", "MEDICATION", "INVESTIGATION", "VITAL", "PROCEDURE"}
        lab = next(entity for entity in extracted["entities"] if entity["entity_type"] == "INVESTIGATION")
        assert lab["abnormal_status"] == "LOW"
        timeline = _expect(client.get(f"/doctor/patients/P1001/timeline"), 403)  # patient must not use clinician timeline endpoint
        assert "permission" in timeline["detail"].casefold()


def test_follow_up_response_persists_alert_and_timeline():
    encounter_id = f"ENC_FOLLOWUP_{uuid4().hex}"
    with TestClient(app) as client:
        with store.connection() as db:
            db.execute(
                """INSERT INTO encounters(encounter_id,patient_id,status,language,stage,revision,ai_provider,started_at,completed_at,finalized_at,care_mode)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (encounter_id, "P1001", "FINALIZED", "en", "FINALIZED", 1, "clinical_rules", now(), now(), now(), "MODERN"),
            )
            for field, value in {"chief_complaint": "chest pain", "medications": ["Metformin 500 mg"]}.items():
                db.execute(
                    """INSERT INTO clinical_facts(fact_id,encounter_id,patient_id,field_name,value_json,source,confidence,status,evidence,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (f"FAC_{uuid4().hex}", encounter_id, "P1001", field, json.dumps(value), "DOCTOR_ENTERED", 1, "VERIFIED", "Synthetic follow-up test", now()),
                )
            plan = create_follow_up_plan(db, patient_id="P1001", encounter_id=encounter_id, created_by="USR_DOCTOR_DEMO", instructions="Continue the clinician-recorded plan.")
        _expect(client.post("/auth/logout"), 204)
        _expect(client.post("/auth/login", json={"email": "patient.demo@medikiosk.local", "password": "DemoPass!2026"}), 200)
        session = _expect(client.post(f"/follow-ups/plans/{plan['follow_up_plan_id']}/sessions"), 201)
        assert session["next_question"]["id"] == "symptom_progress"
        first = _expect(client.post(f"/follow-ups/sessions/{session['session']['follow_up_session_id']}/answers", json={"question_id": "symptom_progress", "message": "I am worse with chest pain and short of breath.", "expected_revision": 0}), 200)
        assert any(alert["severity"] == "EMERGENCY" for alert in first["alerts"])
        with store.connection() as db:
            event = db.execute("SELECT * FROM timeline_events WHERE encounter_id=? AND event_type='FOLLOW_UP_RESPONSE'", (encounter_id,)).fetchone()
            assert event and event["source"] == "PATIENT_REPORTED"
