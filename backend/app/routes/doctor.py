from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, model_validator

from backend.app.clinical_engine import ADDITIONAL_DOCUMENT_FIELDS, AYUSH_FIELDS, QUESTIONS, BOOL_FIELDS, completeness, factual_summary, red_flags
from backend.app.security import AuthenticatedUser, assert_patient_access, current_user, require_roles
from backend.app.store import now, store
from backend.app.clinical_validation import validate_fact
from backend.app.ai.orchestrator import orchestrator

router = APIRouter(prefix="/doctor", tags=["Clinician Review"])


@router.get('/encounters/{encounter_id}/fhir')
def fhir(encounter_id: str, user: AuthenticatedUser = Depends(require_roles('DOCTOR','ADMIN'))):
    from backend.app.fhir_export import export_bundle
    with store.connection() as db:
        encounter = db.execute('SELECT * FROM encounters WHERE encounter_id=?', (encounter_id,)).fetchone()
        if not encounter:
            raise HTTPException(404, 'Encounter not found')
        assert_patient_access(db,user,encounter['patient_id'])
        bundle = export_bundle(db,dict(encounter))
        store.audit(db,user.user_id,'FHIR_EXPORTED','ENCOUNTER',encounter_id)
        return Response(json.dumps(bundle,ensure_ascii=False), media_type='application/fhir+json', headers={'Content-Disposition':f'attachment; filename="{encounter_id}.fhir.json"'})


@router.post('/encounters/{encounter_id}/ai-summary')
def generate_summary(encounter_id: str, user: AuthenticatedUser = Depends(require_roles('DOCTOR','ADMIN'))):
    with store.connection() as db:
        encounter = db.execute('SELECT * FROM encounters WHERE encounter_id=?', (encounter_id,)).fetchone()
        if not encounter:
            raise HTTPException(404, 'Encounter not found')
        assert_patient_access(db, user, encounter['patient_id'])
        state, facts = _state(db, encounter_id)
        cached = db.execute('SELECT result_json FROM ai_summaries WHERE encounter_id=? AND revision=? ORDER BY created_at DESC LIMIT 1', (encounter_id,encounter['revision'])).fetchone()
        if cached:
            return json.loads(cached['result_json'])
    try:
        result = orchestrator.summary.run(facts,state)
    except Exception as exc:
        with store.connection() as db:
            store.audit(db,user.user_id,'AI_SUMMARY_FAILED','ENCOUNTER',encounter_id,{'error_type':type(exc).__name__})
        raise HTTPException(503, 'AI summary is unavailable. The structured clinical record remains available for review.') from exc
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        current = db.execute('SELECT revision FROM encounters WHERE encounter_id=?', (encounter_id,)).fetchone()
        if current['revision'] != encounter['revision']:
            raise HTTPException(409, 'The clinical record changed during summarization. Generate it again.')
        db.execute('INSERT INTO ai_summaries VALUES(?,?,?,?,?,?,?)', (f'SUM_{uuid4().hex}',encounter_id,encounter['revision'],result['provider'],json.dumps(result),now(),user.user_id))
        store.audit(db,user.user_id,'AI_SUMMARY_CREATED','ENCOUNTER',encounter_id,{'provider':result['provider'],'revision':encounter['revision']})
    return result

EDITABLE_FIELDS = {"chief_complaint", "duration", "severity", "location", "character", "radiation", "exertion", "breathlessness", "sweating", "nausea", "past_medical_history", "medications", "allergies"}
EDITABLE_FIELDS.update(set(QUESTIONS) | set(AYUSH_FIELDS) | BOOL_FIELDS | ADDITIONAL_DOCUMENT_FIELDS)


class DoctorCorrection(BaseModel):
    field_name: str = Field(min_length=1, max_length=64)
    value: str | int | bool | list[str]
    reason: str | None = Field(default=None, max_length=500)


class ReconciliationDecision(BaseModel):
    action: str = Field(pattern="^(APPROVED|REJECTED|MERGED)$")
    replacement_value: str | int | bool | list[str] | None = None


class FinalizeInput(BaseModel):
    treatment_plan: str | None = Field(default=None, max_length=2000)
    follow_up_at: str | None = Field(default=None, max_length=40)

    @model_validator(mode='after')
    def require_saved_prescription(self):
        if self.treatment_plan is not None or self.follow_up_at is not None:
            raise ValueError('Save treatment advice and follow-up in the prescription before finalizing')
        return self


def _latest_encounter(db, patient_id: str):
    return db.execute(
        "SELECT * FROM encounters WHERE patient_id=? ORDER BY started_at DESC LIMIT 1", (patient_id,)
    ).fetchone()


def _state(db, encounter_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = db.execute(
        """SELECT * FROM clinical_facts WHERE encounter_id=? AND superseded_at IS NULL
           AND status IN ('REPORTED','VERIFIED') ORDER BY created_at""", (encounter_id,)
    ).fetchall()
    state: dict[str, Any] = {}
    facts: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        value = json.loads(data["value_json"])
        state[data["field_name"]] = value
        facts.append({"fact_id": data["fact_id"], "field_name": data["field_name"], "value": value, "source": data["source"], "confidence": data["confidence"], "status": data["status"], "evidence": data["evidence"], "created_at": data["created_at"]})
    return state, facts


def _unified_summary(state: dict[str, Any], facts: list[dict[str, Any]], document_entities: list[dict[str, Any]], timeline: list[dict[str, Any]], reconciliation: list[dict[str, Any]], flags: list[dict[str, Any]]) -> dict[str, Any]:
    """A source-grounded clinician handoff, assembled without inventing prose."""
    sections: list[dict[str, Any]] = []
    fields = {
        "Chief complaint": ["chief_complaint", "duration", "onset", "severity", "location", "character"],
        "Relevant past medical history": ["past_medical_history", "past_surgical_history", "family_history", "social_history"],
        "Current medications": ["medications"],
        "Allergies": ["allergies"],
        "AYUSH patient-reported history": list(AYUSH_FIELDS),
    }
    by_field = {fact["field_name"]: fact for fact in facts}
    for title, names in fields.items():
        items = [{"field": field, "value": state[field], "source": by_field.get(field, {}).get("source", "NOT_RECORDED")} for field in names if field in state]
        if items:
            sections.append({"title": title, "items": items})
    document_items = [{"type": entity["entity_type"], "value": json.loads(entity["value_json"]), "page": entity["page_number"], "confidence": entity["confidence"], "status": entity["verification_status"]} for entity in document_entities]
    if document_items:
        sections.append({"title": "Relevant document findings", "items": document_items})
    if timeline:
        sections.append({"title": "Important timeline events", "items": [{"title": event["title"], "occurred_at": event["occurred_at"], "source": event["source"], "status": event.get("verification_status", "REPORTED")} for event in timeline[-12:]]})
    return {
        "sections": sections,
        "current_red_flags": flags,
        "missing_information": [name for name in state if state[name] is None],
        "contradictions_requiring_review": [item["field_name"] for item in reconciliation if item["status"] == "OPEN"],
        "source_provenance": [{"field": fact["field_name"], "source": fact["source"], "evidence": fact["evidence"]} for fact in facts],
    }


def _summary(db, patient_id: str) -> dict[str, Any]:
    patient_row = db.execute("SELECT * FROM patients WHERE patient_id=?", (patient_id,)).fetchone()
    if not patient_row:
        raise HTTPException(status_code=404, detail="Patient not found")
    patient = dict(patient_row)
    encounter_row = _latest_encounter(db, patient_id)
    if not encounter_row:
        return {
            "patient_snapshot": {"patient_id": patient_id, "name": patient["name"], "age": patient["age"], "gender": patient["gender"], "preferred_language": patient["language"], "uhid": patient["uhid"], "phone": patient["phone"]},
            "encounter": None, "clinical_state": {}, "facts": [], "completion": {"completion_percentage": 0, "missing": ["chief_complaint"], "critical_missing": ["chief_complaint"], "contradictions": []},
            "red_flags": [], "narrative": "No pre-consultation intake has been started for this patient.", "reconciliation": [], "documents": [], "timeline": [], "follow_up": None, "unified_summary": {"sections": [], "current_red_flags": [], "missing_information": ["chief_complaint"], "contradictions_requiring_review": [], "source_provenance": []}, "verification_status": "NO_ENCOUNTER",
        }
    encounter = dict(encounter_row)
    state, facts = _state(db, encounter["encounter_id"])
    quality = completeness(state, encounter.get("care_mode", "MODERN"))
    flags = [dict(row) | {"evidence": json.loads(row["evidence_json"])} for row in db.execute("SELECT * FROM red_flags WHERE encounter_id=? AND resolved_at IS NULL ORDER BY created_at", (encounter["encounter_id"],)).fetchall()]
    reconciliation = [dict(row) | {"incoming_value": json.loads(row["incoming_value_json"])} for row in db.execute("SELECT * FROM reconciliation_items WHERE encounter_id=? ORDER BY created_at DESC", (encounter["encounter_id"],)).fetchall()]
    documents = [dict(row) for row in db.execute("""SELECT d.*,COUNT(e.entity_id) AS entity_count FROM documents d LEFT JOIN document_entities e ON e.document_id=d.document_id WHERE d.encounter_id=? GROUP BY d.document_id ORDER BY d.uploaded_at DESC""", (encounter["encounter_id"],)).fetchall()]
    timeline = [dict(row) | {"metadata": json.loads(row["metadata_json"] or "{}") if "metadata_json" in row.keys() else {}} for row in db.execute("SELECT * FROM timeline_events WHERE patient_id=? ORDER BY occurred_at", (patient_id,)).fetchall()]
    document_entities = [dict(row) for row in db.execute("SELECT e.* FROM document_entities e JOIN documents d ON d.document_id=e.document_id WHERE d.encounter_id=? ORDER BY d.document_date,e.page_number", (encounter["encounter_id"],))]
    plan_row = db.execute("SELECT * FROM follow_up_plans WHERE encounter_id=?", (encounter["encounter_id"],)).fetchone()
    follow_up = None
    if plan_row:
        plan = dict(plan_row)
        last_session = db.execute("SELECT * FROM follow_up_sessions WHERE follow_up_plan_id=? ORDER BY started_at DESC LIMIT 1", (plan["follow_up_plan_id"],)).fetchone()
        last_response = db.execute("SELECT r.* FROM follow_up_responses r JOIN follow_up_sessions s ON s.follow_up_session_id=r.follow_up_session_id WHERE s.follow_up_plan_id=? ORDER BY r.created_at DESC LIMIT 1", (plan["follow_up_plan_id"],)).fetchone()
        alerts = [dict(row) for row in db.execute("SELECT a.* FROM follow_up_alerts a JOIN follow_up_sessions s ON s.follow_up_session_id=a.follow_up_session_id WHERE s.follow_up_plan_id=? AND a.status='OPEN' ORDER BY a.created_at DESC", (plan["follow_up_plan_id"],))]
        follow_up = {"plan": plan, "last_session": dict(last_session) if last_session else None, "last_response": dict(last_response) if last_response else None, "open_alerts": alerts}
    return {
        "patient_snapshot": {"patient_id": patient_id, "name": patient["name"], "age": patient["age"], "gender": patient["gender"], "preferred_language": patient["language"], "uhid": patient["uhid"], "phone": patient["phone"]},
        "encounter": {key: encounter[key] for key in ("encounter_id", "status", "language", "stage", "revision", "started_at", "completed_at", "finalized_at", "ai_provider", "care_mode")},
        "clinical_state": state, "facts": facts, "completion": quality, "red_flags": flags,
        "narrative": factual_summary(state, quality, red_flags(state)), "reconciliation": reconciliation,
        "documents": documents, "timeline": timeline, "follow_up": follow_up, "unified_summary": _unified_summary(state, facts, document_entities, timeline, reconciliation, flags), "verification_status": "FINALIZED" if encounter["status"] == "FINALIZED" else "DOCTOR_REVIEW_REQUIRED",
    }


@router.get("/patients")
def queue(user: AuthenticatedUser = Depends(require_roles("DOCTOR", "ADMIN"))):
    with store.connection() as db:
        if user.role == "DOCTOR":
            patients = db.execute("SELECT p.* FROM patients p JOIN clinician_assignments a ON a.patient_id=p.patient_id WHERE a.doctor_user_id=? ORDER BY p.updated_at DESC", (user.user_id,)).fetchall()
        else:
            patients = db.execute("SELECT * FROM patients ORDER BY updated_at DESC").fetchall()
        result = []
        for patient in patients:
            patient_data = dict(patient)
            encounter = _latest_encounter(db, patient_data["patient_id"])
            if encounter:
                state, _ = _state(db, encounter["encounter_id"])
                flags = red_flags(state) + [dict(row) for row in db.execute('SELECT severity FROM red_flags WHERE encounter_id=? AND resolved_at IS NULL', (encounter['encounter_id'],))]
                result.append({"patient_id": patient_data["patient_id"], "name": patient_data["name"], "age": patient_data["age"], "gender": patient_data["gender"], "language": patient_data["language"], "interview_id": encounter["encounter_id"], "current_complaint": state.get("chief_complaint"), "duration": state.get("duration"), "severity": state.get("severity"), "status": encounter["status"], "priority": max((flag["severity"] for flag in flags), key=lambda level:{'NORMAL':0,'INFO':1,'MODERATE':2,'HIGH':3,'EMERGENCY':4}[level], default="NORMAL"), "updated_at": encounter["started_at"]})
            else:
                result.append({"patient_id": patient_data["patient_id"], "name": patient_data["name"], "age": patient_data["age"], "gender": patient_data["gender"], "language": patient_data["language"], "current_complaint": None, "status": "NO_ENCOUNTER", "priority": "NORMAL"})
        store.audit(db, user.user_id, "DOCTOR_QUEUE_VIEWED", "PATIENT_QUEUE", user.user_id)
        return result


@router.get("/patients/{patient_id}/summary")
def summary(patient_id: str, user: AuthenticatedUser = Depends(require_roles("DOCTOR", "ADMIN"))):
    with store.connection() as db:
        assert_patient_access(db, user, patient_id)
        response = _summary(db, patient_id)
        store.audit(db, user.user_id, "CLINICAL_SUMMARY_VIEWED", "PATIENT", patient_id)
        return response


@router.post("/patients/{patient_id}/facts")
def correct(patient_id: str, correction: DoctorCorrection, user: AuthenticatedUser = Depends(require_roles("DOCTOR", "ADMIN"))):
    correction.value = validate_fact(correction.field_name, correction.value)
    if correction.field_name not in EDITABLE_FIELDS:
        raise HTTPException(status_code=422, detail="This field cannot be corrected through this endpoint")
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        assert_patient_access(db, user, patient_id)
        encounter = _latest_encounter(db, patient_id)
        if not encounter:
            raise HTTPException(status_code=409, detail="A clinical encounter is required before correction")
        if encounter["status"] != "SUBMITTED":
            raise HTTPException(409, "Only submitted encounters may be corrected; finalized records are locked")
        current = db.execute("SELECT * FROM clinical_facts WHERE encounter_id=? AND field_name=? AND superseded_at IS NULL ORDER BY created_at DESC LIMIT 1", (encounter["encounter_id"], correction.field_name)).fetchone()
        old_value = json.loads(current["value_json"]) if current else None
        if current:
            db.execute("UPDATE clinical_facts SET superseded_at=? WHERE fact_id=?", (now(), current["fact_id"]))
        fact_id = f"FAC_{uuid4().hex}"
        db.execute("INSERT INTO clinical_facts(fact_id,encounter_id,patient_id,field_name,value_json,source,confidence,status,evidence,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (fact_id, encounter["encounter_id"], patient_id, correction.field_name, json.dumps(correction.value), "DOCTOR_ENTERED", 1.0, "VERIFIED", correction.reason, now()))
        db.execute(
            """INSERT INTO timeline_events(event_id,patient_id,encounter_id,event_type,title,detail,source,confidence,occurred_at,created_at,verification_status,metadata_json)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (f"EVT_{uuid4().hex}", patient_id, encounter["encounter_id"], "DOCTOR_VERIFIED_FACT", f"Clinician verified {correction.field_name.replace('_', ' ')}", str(correction.value)[:1000], "DOCTOR_ENTERED", 1.0, now(), now(), "VERIFIED", json.dumps({"fact_id": fact_id, "reason": correction.reason})),
        )
        db.execute("UPDATE encounters SET status='SUBMITTED',revision=revision+1 WHERE encounter_id=?", (encounter["encounter_id"],))
        store.audit(db, user.user_id, "DOCTOR_CORRECTED_FACT", "CLINICAL_FACT", fact_id, {"field": correction.field_name})
        return {"fact_id": fact_id, "field_name": correction.field_name, "previous_value": old_value, "value": correction.value, "provenance": "DOCTOR_ENTERED"}


@router.post("/encounters/{encounter_id}/finalize")
def finalize(encounter_id: str, payload: FinalizeInput | None = None, user: AuthenticatedUser = Depends(require_roles("DOCTOR"))):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT * FROM encounters WHERE encounter_id=?", (encounter_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Encounter not found")
        encounter = dict(row)
        assert_patient_access(db, user, encounter["patient_id"])
        if encounter["status"] != "SUBMITTED":
            raise HTTPException(409, "Only a patient-submitted encounter can be finalized")
        state, _ = _state(db, encounter_id)
        if completeness(state, encounter.get("care_mode", "MODERN"))["critical_missing"]:
            raise HTTPException(409, "Critical clinical fields are missing")
        open_items = db.execute("SELECT COUNT(*) AS count FROM reconciliation_items WHERE encounter_id=? AND status='OPEN'", (encounter_id,)).fetchone()["count"]
        if open_items:
            raise HTTPException(status_code=409, detail="Resolve document reconciliation items before finalizing")
        from backend.app.routes.records import prescription_record, snapshot_record, recorded_allergies
        prescription = prescription_record(db, encounter_id)
        if not prescription:
            raise HTTPException(409, 'Save a prescription or an explicit no-medicines plan before finalizing')
        review = prescription.get('allergy_review')
        if prescription['medicines'] and (not review or review['allergies'] != recorded_allergies(db, encounter_id)):
            raise HTTPException(409, 'Review the current allergy information and save the prescription again before finalizing')
        db.execute("UPDATE encounters SET status='FINALIZED',stage='FINALIZED',finalized_at=?,revision=revision+1 WHERE encounter_id=?", (now(), encounter_id))
        db.execute("INSERT INTO timeline_events(event_id,patient_id,encounter_id,event_type,title,detail,source,confidence,occurred_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (f"EVT_{uuid4().hex}", encounter["patient_id"], encounter_id, "ENCOUNTER_FINALIZED", "Clinician finalized intake", "Final clinical verification completed.", "DOCTOR_ENTERED", 1.0, now(), now()))
        from backend.app.routes.followups import create_follow_up_plan
        plan = create_follow_up_plan(
            db,
            patient_id=encounter["patient_id"],
            encounter_id=encounter_id,
            created_by=user.user_id,
            instructions=prescription['advice'],
            follow_up_at=prescription['follow_up_at'],
        )
        snapshot_record(db, encounter_id, user)
        store.audit(db, user.user_id, "ENCOUNTER_FINALIZED", "ENCOUNTER", encounter_id)
        return {"encounter_id": encounter_id, "status": "FINALIZED", "finalized_by": user.display_name, "finalized_at": now(), "follow_up_plan_id": plan["follow_up_plan_id"]}


@router.get("/patients/{patient_id}/timeline")
def timeline(patient_id: str, user: AuthenticatedUser = Depends(require_roles("DOCTOR", "ADMIN"))):
    with store.connection() as db:
        assert_patient_access(db, user, patient_id)
        events = [dict(row) for row in db.execute("SELECT * FROM timeline_events WHERE patient_id=? ORDER BY occurred_at", (patient_id,)).fetchall()]
        store.audit(db, user.user_id, "TIMELINE_VIEWED", "PATIENT", patient_id)
        return events


@router.get("/patients/{patient_id}/audit")
def patient_audit(patient_id: str, user: AuthenticatedUser = Depends(require_roles("DOCTOR", "ADMIN"))):
    with store.connection() as db:
        assert_patient_access(db, user, patient_id)
        encounter = _latest_encounter(db, patient_id)
        if not encounter:
            return []
        rows = [dict(row) | {"metadata": json.loads(row["metadata_json"])} for row in db.execute(
            "SELECT * FROM audit_logs WHERE resource_type IN ('CLINICAL_FACT','RECONCILIATION','ENCOUNTER') ORDER BY created_at DESC", ()
        ).fetchall()]
        # Audit metadata deliberately contains no raw patient answers; retain only entries
        # tied to facts belonging to this patient's latest encounter where possible.
        fact_ids = {row["fact_id"] for row in db.execute("SELECT fact_id FROM clinical_facts WHERE encounter_id=?", (encounter["encounter_id"],)).fetchall()}
        reconciliation_ids = {row['reconciliation_id'] for row in db.execute('SELECT reconciliation_id FROM reconciliation_items WHERE encounter_id=?', (encounter['encounter_id'],))}
        return [row for row in rows if row["resource_id"] in fact_ids | reconciliation_ids or row["resource_id"] == encounter["encounter_id"]]


@router.get("/encounters/{encounter_id}/reconciliation")
def reconciliations(encounter_id: str, user: AuthenticatedUser = Depends(require_roles("DOCTOR", "ADMIN"))):
    with store.connection() as db:
        encounter = db.execute("SELECT * FROM encounters WHERE encounter_id=?", (encounter_id,)).fetchone()
        if not encounter:
            raise HTTPException(status_code=404, detail="Encounter not found")
        assert_patient_access(db, user, encounter["patient_id"])
        return [dict(row) | {"incoming_value": json.loads(row["incoming_value_json"])} for row in db.execute("SELECT * FROM reconciliation_items WHERE encounter_id=? ORDER BY created_at DESC", (encounter_id,)).fetchall()]


@router.post("/reconciliation/{item_id}")
def reconcile(item_id: str, decision: ReconciliationDecision, user: AuthenticatedUser = Depends(require_roles("DOCTOR", "ADMIN"))):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        item_row = db.execute("SELECT * FROM reconciliation_items WHERE reconciliation_id=?", (item_id,)).fetchone()
        if not item_row:
            raise HTTPException(status_code=404, detail="Reconciliation item not found")
        item = dict(item_row)
        encounter = db.execute("SELECT * FROM encounters WHERE encounter_id=?", (item["encounter_id"],)).fetchone()
        assert_patient_access(db, user, encounter["patient_id"])
        if item["status"] != "OPEN":
            raise HTTPException(status_code=409, detail="This reconciliation item has already been resolved")
        if encounter["status"] == "FINALIZED":
            raise HTTPException(409, "Finalized records cannot be changed")
        value = decision.replacement_value if decision.replacement_value is not None else json.loads(item["incoming_value_json"])
        if decision.action in {"APPROVED", "MERGED"}:
            value = validate_fact(item["field_name"], value)
            if decision.action == "MERGED" and decision.replacement_value is None:
                raise HTTPException(422, "Provide the reviewed merged value explicitly")
            current = db.execute("SELECT * FROM clinical_facts WHERE encounter_id=? AND field_name=? AND superseded_at IS NULL ORDER BY created_at DESC LIMIT 1", (item["encounter_id"], item["field_name"])).fetchone()
            if current:
                db.execute("UPDATE clinical_facts SET superseded_at=? WHERE fact_id=?", (now(), current["fact_id"]))
            evidence = item.get("evidence") or f"Reconciled from {item['incoming_source']}"
            db.execute("INSERT INTO clinical_facts(fact_id,encounter_id,patient_id,field_name,value_json,source,confidence,status,evidence,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (f"FAC_{uuid4().hex}", item["encounter_id"], encounter["patient_id"], item["field_name"], json.dumps(value), item["incoming_source"], 1.0, "VERIFIED", evidence, now()))
        db.execute("UPDATE reconciliation_items SET status=?,resolved_at=?,resolved_by=? WHERE reconciliation_id=?", (decision.action, now(), user.user_id, item_id))
        if item.get("document_id"):
            verification = "REJECTED" if decision.action == "REJECTED" else "VERIFIED"
            db.execute("UPDATE document_entities SET verification_status=?,updated_at=? WHERE document_id=? AND field_name=?", (verification, now(), item["document_id"], item["field_name"]))
            entity_types = {row['entity_type'] for row in db.execute('SELECT DISTINCT entity_type FROM document_entities WHERE document_id=? AND field_name=?', (item['document_id'], item['field_name']))}
            for entity_type in entity_types:
                db.execute('UPDATE timeline_events SET verification_status=? WHERE encounter_id=? AND document_id=? AND event_type=?',
                           ('RECONCILED' if decision.action == 'MERGED' else verification, item['encounter_id'], item['document_id'], f'DOCUMENT_{entity_type}'))
        db.execute('INSERT INTO timeline_events(event_id,patient_id,encounter_id,event_type,title,detail,source,confidence,occurred_at,created_at,document_id,page_number,verification_status,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (f'EVT_{uuid4().hex}', encounter['patient_id'], item['encounter_id'], 'RECONCILIATION_RESOLVED', f'Clinician reviewed {item["field_name"].replace("_", " ")}',
                    f'{decision.action}: {value}', 'DOCTOR_ENTERED', 1.0, now(), now(), item.get('document_id'), item.get('page_number'), 'VERIFIED', json.dumps({'reconciliation_id': item_id, 'decision': decision.action})))
        db.execute("UPDATE encounters SET revision=revision+1 WHERE encounter_id=?", (item["encounter_id"],))
        store.audit(db, user.user_id, "RECONCILIATION_RESOLVED", "RECONCILIATION", item_id, {"action": decision.action})
        return {"reconciliation_id": item_id, "status": decision.action}
