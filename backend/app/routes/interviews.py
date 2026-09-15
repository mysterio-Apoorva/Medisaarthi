from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from backend.app.ai.providers import safe_extract
from backend.app.clinical_engine import completeness, factual_summary, next_question, red_flags, stage_for
from backend.app.security import AuthenticatedUser, assert_patient_access, current_user
from backend.app.store import now, store
from backend.app.voice import SpeechToTextUnavailable, transcribe_upload
from backend.app.clinical_validation import validate_fact
from backend.app.ai.orchestrator import orchestrator
from backend.app.question_budget import budget, plan_question, record_candidates, MIN_QUESTIONS
from backend.app.ai.questions import phrase_question

router = APIRouter(prefix="/interviews", tags=["Clinical Intake"])


class ConsentInput(BaseModel):
    patient_id: str = Field(min_length=1, max_length=64)
    consent_type: Literal["CLINICAL_INTAKE", "DOCUMENT_PROCESSING"] = "CLINICAL_INTAKE"
    version: str = Field(default="2026-09", min_length=1, max_length=32)
    purpose: str = Field(default="AI-assisted pre-consultation history taking", min_length=5, max_length=500)


class StartInput(BaseModel):
    patient_id: str = Field(min_length=1, max_length=64)
    language: Literal["en", "hi"] = "en"
    consent_id: str = Field(min_length=1, max_length=80)
    care_mode: Literal["MODERN", "AYUSH"] = "MODERN"
    processing_mode: Literal['AI', 'MANUAL'] = 'AI'


class ModeInput(BaseModel):
    processing_mode: Literal['AI', 'MANUAL']


@router.patch('/{encounter_id}/mode')
def change_mode(encounter_id: str, payload: ModeInput, user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM encounters WHERE encounter_id=?', (encounter_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Encounter not found')
        assert_patient_access(db, user, row['patient_id'])
        if user.role != 'PATIENT' or row['status'] != 'ACTIVE':
            raise HTTPException(409, 'Only an active patient interview can change processing mode')
        db.execute('UPDATE encounters SET processing_mode=?,pending_question_json=NULL,revision=revision+1 WHERE encounter_id=?', (payload.processing_mode, encounter_id))
        store.audit(db, user.user_id, 'INTAKE_MODE_CHANGED', 'ENCOUNTER', encounter_id, {'mode': payload.processing_mode})
        return {'processing_mode': payload.processing_mode, 'revision': row['revision'] + 1}


class AnswerInput(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    expected_revision: int | None = Field(default=None, ge=0)


class SubmitInput(BaseModel):
    expected_revision: int | None = Field(default=None, ge=0)
    reviewed: bool = False


class PatientCorrection(BaseModel):
    field_name: str
    value: str | int | bool | list[str]
    expected_revision: int = Field(ge=0)


@router.post("/{encounter_id}/corrections")
def correct_patient_fact(encounter_id: str, payload: PatientCorrection, user: AuthenticatedUser = Depends(current_user)):
    value = validate_fact(payload.field_name, payload.value)
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM encounters WHERE encounter_id=?", (encounter_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Encounter not found")
        assert_patient_access(db, user, row["patient_id"])
        if user.role != "PATIENT" or row["status"] not in {"ACTIVE", "PATIENT_REVIEW"}:
            raise HTTPException(409, "This record is no longer open for patient correction")
        if row["revision"] != payload.expected_revision:
            raise HTTPException(409, "The record changed. Reload before correcting it.")
        _write_fact(db, encounter_id, row["patient_id"], {"field_name": payload.field_name, "value": value, "confidence": 1.0, "evidence": "Explicit patient correction during review"}, "PATIENT_REPORTED")
        corrected_state = _state(db, encounter_id)
        _set_flags(db, encounter_id, red_flags(corrected_state), preserve=True)
        next_q = _planned_question(db, dict(row), corrected_state, refresh=True)
        db.execute("UPDATE encounters SET revision=revision+1,status=?,stage=? WHERE encounter_id=?", ('ACTIVE' if next_q else 'PATIENT_REVIEW',stage_for(corrected_state,row['care_mode']) if next_q else 'PATIENT_REVIEW',encounter_id))
        store.audit(db, user.user_id, "PATIENT_CORRECTED_FACT", "ENCOUNTER", encounter_id, {"field": payload.field_name})
        return {"revision": row["revision"] + 1}


def _state(db, encounter_id: str) -> dict[str, Any]:
    rows = db.execute(
        """SELECT field_name,value_json FROM clinical_facts
           WHERE encounter_id=? AND superseded_at IS NULL AND status IN ('REPORTED','VERIFIED')
           ORDER BY created_at ASC""",
        (encounter_id,),
    ).fetchall()
    result: dict[str, Any] = {}
    for row in rows:
        result[row["field_name"]] = json.loads(row["value_json"])
    return result


def _answers(db, encounter_id):
    return [dict(row) for row in db.execute('SELECT * FROM answers WHERE encounter_id=? ORDER BY created_at', (encounter_id,)).fetchall()]


def _planned_question(db, encounter, state, refresh=False):
    state = {**state, '_unresolved_safety': bool(db.execute('SELECT 1 FROM red_flags WHERE encounter_id=? AND resolved_at IS NULL LIMIT 1', (encounter['encounter_id'],)).fetchone())}
    answers = _answers(db, encounter['encounter_id'])
    if budget(state, answers, encounter.get('care_mode', 'MODERN'))['complete']:
        return None
    if encounter.get('pending_question_json') and not refresh:
        return json.loads(encounter['pending_question_json'])
    question = plan_question(state, encounter['language'], encounter.get('care_mode', 'MODERN'), answers,
                             record_candidates(db, encounter['patient_id'], encounter['encounter_id']))
    encoded = json.dumps(question, ensure_ascii=False) if question else None
    db.execute('UPDATE encounters SET pending_question_json=? WHERE encounter_id=?', (encoded, encounter['encounter_id']))
    encounter['pending_question_json'] = encoded
    return question


def _deliver_question(result):
    """Inference never holds a database write lock; saving an answer and asking are distinct."""
    question = result.get('next_question')
    if not question or question.get('generation_method'):
        return result
    try:
        generated = phrase_question(question, result['clinical_state'], result['language'], result['encounter'].get('processing_mode') == 'MANUAL')
    except HTTPException as exc:
        result['next_question'] = {**question, 'text': '', 'generation_method': 'UNAVAILABLE'}
        result['ai_warning'] = str(exc.detail)
        return result
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        current = db.execute('SELECT revision,status,pending_question_json FROM encounters WHERE encounter_id=?', (result['encounter_id'],)).fetchone()
        if current['revision'] != result['revision'] or current['status'] != 'ACTIVE':
            raise HTTPException(409, 'The interview changed while generating a question. Reload the saved record.')
        stored = json.loads(current['pending_question_json']) if current['pending_question_json'] else None
        if stored and stored.get('generation_method'):
            generated = stored
        else:
            db.execute('UPDATE encounters SET pending_question_json=? WHERE encounter_id=?', (json.dumps(generated, ensure_ascii=False), result['encounter_id']))
    result['next_question'] = generated
    result['encounter']['pending_question_json'] = json.dumps(generated, ensure_ascii=False)
    return result


_TIMELINE_FACT_LABELS = {
    "chief_complaint": "Patient reports current concern",
    "past_medical_history": "Patient reports past medical history",
    "past_surgical_history": "Patient reports procedure or admission history",
    "medications": "Patient reports medication history",
    "allergies": "Patient reports allergy information",
    "ahara_vihara": "Patient reports AYUSH food and lifestyle history",
    "prakriti": "Patient-reported AYUSH constitution description",
    "vikriti": "Patient-reported AYUSH current imbalance description",
}


def _record_fact_timeline(db, *, fact_id: str, encounter_id: str, patient_id: str, field_name: str, value: Any, source: str, evidence: str | None) -> None:
    label = _TIMELINE_FACT_LABELS.get(field_name)
    if not label:
        return
    display = ", ".join(str(item) for item in value) if isinstance(value, list) else str(value)
    title = f"{label}: {display}"[:500]
    duplicate = db.execute(
        "SELECT 1 FROM timeline_events WHERE encounter_id=? AND event_type=? AND title=? LIMIT 1",
        (encounter_id, f"INTERVIEW_{field_name.upper()}", title),
    ).fetchone()
    if duplicate:
        return
    db.execute(
        """INSERT INTO timeline_events(event_id,patient_id,encounter_id,event_type,title,detail,source,confidence,occurred_at,created_at,verification_status,metadata_json)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (f"EVT_{uuid4().hex}", patient_id, encounter_id, f"INTERVIEW_{field_name.upper()}", title, "Recorded during the patient intake conversation.", source, 0.88 if source == "AI_EXTRACTION" else 1.0, now(), now(), "REPORTED", json.dumps({"fact_id": fact_id, "evidence": evidence}, ensure_ascii=False)),
    )


def _write_fact(db, encounter_id: str, patient_id: str, fact: dict[str, Any], source: str = "AI_EXTRACTION") -> bool:
    field_name = fact["field_name"]
    existing = db.execute(
        "SELECT fact_id,value_json FROM clinical_facts WHERE encounter_id=? AND field_name=? AND superseded_at IS NULL ORDER BY created_at DESC LIMIT 1",
        (encounter_id, field_name),
    ).fetchone()
    encoded = json.dumps(fact["value"], ensure_ascii=False)
    if existing and existing["value_json"] == encoded:
        return True
    if existing and source != 'PATIENT_REPORTED':
        duplicate = db.execute("SELECT 1 FROM reconciliation_items WHERE encounter_id=? AND field_name=? AND incoming_value_json=? AND status='OPEN'", (encounter_id,field_name,encoded)).fetchone()
        if not duplicate:
            db.execute("INSERT INTO reconciliation_items(reconciliation_id,encounter_id,field_name,current_fact_id,incoming_value_json,incoming_source,confidence,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (f'REC_{uuid4().hex}',encounter_id,field_name,existing['fact_id'],encoded,source,float(fact.get('confidence',0)), 'OPEN',now()))
        return False
    if existing:
        db.execute("UPDATE clinical_facts SET superseded_at=? WHERE fact_id=?", (now(), existing["fact_id"]))
    fact_id = f"FAC_{uuid4().hex}"
    db.execute(
        """INSERT INTO clinical_facts(fact_id,encounter_id,patient_id,field_name,value_json,source,confidence,status,evidence,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (fact_id, encounter_id, patient_id, field_name, encoded, source, float(fact.get("confidence", 0.88)), "REPORTED", fact.get("evidence"), now()),
    )
    _record_fact_timeline(db, fact_id=fact_id, encounter_id=encounter_id, patient_id=patient_id, field_name=field_name, value=fact["value"], source=source, evidence=fact.get("evidence"))
    return True


def _set_flags(db, encounter_id: str, flags: list[dict[str, Any]], preserve=False) -> None:
    if not preserve:
        db.execute("DELETE FROM red_flags WHERE encounter_id=? AND resolved_at IS NULL", (encounter_id,))
    for flag in flags:
        if db.execute('SELECT 1 FROM red_flags WHERE encounter_id=? AND rule_code=? AND resolved_at IS NULL', (encounter_id, flag['code'])).fetchone():
            continue
        db.execute(
            "INSERT INTO red_flags(flag_id,encounter_id,rule_code,severity,message,evidence_json,created_at) VALUES(?,?,?,?,?,?,?)",
            (f"FLG_{uuid4().hex}", encounter_id, flag["code"], flag["severity"], flag["message"], json.dumps(flag["evidence"]), now()),
        )


def _response(db, encounter: dict[str, Any], extracted: list[dict[str, Any]] | None = None, ai_error: str | None = None) -> dict[str, Any]:
    state = _state(db, encounter["encounter_id"])
    evaluation = orchestrator.evaluate(state, encounter["language"], encounter.get("care_mode", "MODERN"))
    quality, flags = evaluation['completion'], evaluation['flags']
    persisted_flags = [dict(row) for row in db.execute('SELECT rule_code AS code,severity,message,evidence_json FROM red_flags WHERE encounter_id=? AND resolved_at IS NULL', (encounter['encounter_id'],)).fetchall()]
    flags = list({f['code']: f for f in [*flags, *persisted_flags]}.values())
    question = _planned_question(db, encounter, state) if encounter['status'] == 'ACTIVE' else None
    question_budget = budget({**state, '_unresolved_safety': bool(flags)}, _answers(db, encounter['encounter_id']), encounter.get('care_mode', 'MODERN'))
    # Resuming a pre-upgrade encounter must not strand a patient at the new cap.
    if encounter['status'] == 'ACTIVE' and question_budget['complete']:
        db.execute("UPDATE encounters SET status='PATIENT_REVIEW',stage='PATIENT_REVIEW',pending_question_json=NULL WHERE encounter_id=? AND status='ACTIVE'", (encounter['encounter_id'],))
        encounter.update(status='PATIENT_REVIEW', stage='PATIENT_REVIEW', pending_question_json=None)
        question = None
    quality['contradictions'] = [row['field_name'] for row in db.execute("SELECT DISTINCT field_name FROM reconciliation_items WHERE encounter_id=? AND status='OPEN'", (encounter['encounter_id'],)).fetchall()]
    return {
        "interview_id": encounter["encounter_id"], "encounter_id": encounter["encounter_id"], "patient_id": encounter["patient_id"],
        "status": encounter["status"], "revision": encounter["revision"], "clinical_state": state,
        "language": encounter["language"], "encounter": encounter,
        "extracted_facts": extracted or [], "next_question": question, "current_topic": question["id"] if question else "patient_review",
        "stage": stage_for(state, encounter.get("care_mode", "MODERN")), "completion": quality, "priority_flags": flags,
        "interview_completed": encounter["status"] in {"PATIENT_REVIEW", "SUBMITTED", "FINALIZED"},
        "ai_warning": ai_error,
        "question_budget": question_budget,
        "answers": _answers(db, encounter['encounter_id']),
    }


@router.post("/consents", status_code=status.HTTP_201_CREATED)
def record_consent(payload: ConsentInput, user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        assert_patient_access(db, user, payload.patient_id)
        if user.role != "PATIENT":
            raise HTTPException(status_code=403, detail="Only the patient may record their consent")
        consent_id = f"CON_{uuid4().hex}"
        db.execute(
            "INSERT INTO consents(consent_id,patient_id,consent_type,version,purpose,status,recorded_by,recorded_at) VALUES(?,?,?,?,?,?,?,?)",
            (consent_id, payload.patient_id, payload.consent_type, payload.version, payload.purpose, "GRANTED", user.user_id, now()),
        )
        store.audit(db, user.user_id, "CONSENT_GRANTED", "CONSENT", consent_id, {"type": payload.consent_type, "version": payload.version})
    return {"consent_id": consent_id, "status": "GRANTED", "version": payload.version}


@router.post("/start", status_code=status.HTTP_201_CREATED)
def start(payload: StartInput, user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        assert_patient_access(db, user, payload.patient_id)
        if user.role != "PATIENT":
            raise HTTPException(status_code=403, detail="Only the patient may start their own intake")
        consent = db.execute(
            "SELECT * FROM consents WHERE consent_id=? AND patient_id=? AND consent_type='CLINICAL_INTAKE' AND status='GRANTED'",
            (payload.consent_id, payload.patient_id),
        ).fetchone()
        if not consent:
            raise HTTPException(status_code=409, detail="A current clinical intake consent is required")
        if consent["encounter_id"]:
            existing = dict(db.execute("SELECT * FROM encounters WHERE encounter_id=?", (consent["encounter_id"],)).fetchone())
            if payload.processing_mode == 'MANUAL' and existing['status'] == 'ACTIVE' and existing['processing_mode'] != 'MANUAL':
                db.execute("UPDATE encounters SET processing_mode='MANUAL',pending_question_json=NULL,revision=revision+1 WHERE encounter_id=?", (existing['encounter_id'],))
                existing.update(processing_mode='MANUAL', pending_question_json=None, revision=existing['revision'] + 1)
            result = _response(db, existing)
            db.commit()
            result = _deliver_question(result)
            return {"message": "Existing interview resumed", "initial_question": result["next_question"], **result}
        encounter_id = f"ENC_{uuid4().hex}"
        db.execute(
            "INSERT INTO encounters(encounter_id,patient_id,status,language,stage,revision,ai_provider,started_at,care_mode,processing_mode) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (encounter_id, payload.patient_id, "ACTIVE", payload.language, "CHIEF_COMPLAINT", 0, os.getenv("AI_PROVIDER", "ollama"), now(), payload.care_mode, payload.processing_mode),
        )
        db.execute("UPDATE consents SET encounter_id=? WHERE consent_id=?", (encounter_id, payload.consent_id))
        db.execute(
            "INSERT INTO timeline_events(event_id,patient_id,encounter_id,event_type,title,detail,source,confidence,occurred_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (f"EVT_{uuid4().hex}", payload.patient_id, encounter_id, "ENCOUNTER_STARTED", "AI-assisted intake started", "Patient began a structured pre-consultation history.", "PATIENT_REPORTED", 1.0, now(), now()),
        )
        store.audit(db, user.user_id, "ENCOUNTER_STARTED", "ENCOUNTER", encounter_id)
        encounter = dict(db.execute("SELECT * FROM encounters WHERE encounter_id=?", (encounter_id,)).fetchone())
        result = _response(db, encounter)
    result = _deliver_question(result)
    return {"message": "Interview started", "initial_question": result["next_question"], **result}


@router.post("/{encounter_id}/answers")
def answer(encounter_id: str, payload: AnswerInput, user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        encounter_row = db.execute("SELECT * FROM encounters WHERE encounter_id=?", (encounter_id,)).fetchone()
        if not encounter_row:
            raise HTTPException(status_code=404, detail="Encounter not found")
        encounter = dict(encounter_row)
        assert_patient_access(db, user, encounter["patient_id"])
        if user.role != "PATIENT" or encounter["status"] != "ACTIVE":
            raise HTTPException(status_code=409, detail="This encounter is not accepting patient answers")
        if payload.expected_revision is not None and payload.expected_revision != encounter["revision"]:
            raise HTTPException(status_code=409, detail="This response is stale. Refresh the interview before continuing.")
        state = _state(db, encounter_id)
        question = _planned_question(db, encounter, state)
        if question is None:
            raise HTTPException(status_code=409, detail="The interview is ready for patient review")
        clean_answer = payload.message.strip()
        if not clean_answer:
            raise HTTPException(status_code=422, detail="Please provide an answer before continuing")
    # Model inference must not hold the SQLite write lock. Recheck after inference.
    try:
        interpretation = orchestrator.interpret(clean_answer, question["id"], {**state, '_question_fields': question.get('fields', [question['id']])}, manual=encounter.get('processing_mode') == 'MANUAL')
    except Exception as exc:
        raise HTTPException(503, 'AI processing is unavailable. Your answer has not been saved. Retry or select manual intake.') from exc
    extraction, provider, ai_error = interpretation.extraction, interpretation.provider, interpretation.warning
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        latest = db.execute("SELECT revision,status FROM encounters WHERE encounter_id=?", (encounter_id,)).fetchone()
        if latest["revision"] != encounter["revision"] or latest["status"] != "ACTIVE":
            raise HTTPException(status_code=409, detail="The interview changed. Refresh before sending this answer again.")
        db.execute(
            "INSERT INTO answers(answer_id,encounter_id,question_id,question_text,answer_text,source,created_at) VALUES(?,?,?,?,?,?,?)",
            (f"ANS_{uuid4().hex}", encounter_id, question["id"], question["text"], clean_answer, "PATIENT_REPORTED", now()),
        )
        extracted = []
        confirmation = question.get('confirmation')
        confirmation_answer = ' '.join(clean_answer.casefold().translate(str.maketrans('', '', '.,!?।')).split())
        if confirmation and confirmation_answer in {'no', 'no that is wrong', 'no that is not correct', 'नहीं'}:
            # Rejecting an old report does not establish absence of current medication/allergy.
            extraction.facts = [f for f in extraction.facts if f.field_name != question['id']]
        if confirmation and confirmation_answer in {'yes', 'yes still correct', 'yes that is correct', 'yes it is', 'yes i still take it', 'yes i am still taking it', 'correct', 'हाँ', 'हां', 'जी हाँ', 'हाँ सही है'}:
            value = validate_fact(question['id'], confirmation['value'])
            # Patient confirmation preserves the original document and its clinician reconciliation.
            fact = {'field_name': question['id'], 'value': value, 'confidence': 1.,
                    'evidence': f"Patient confirmed {confirmation['source']} {confirmation.get('document_id', confirmation.get('fact_id', ''))}: {clean_answer}"}
            _write_fact(db, encounter_id, encounter['patient_id'], fact, 'PATIENT_REPORTED')
            extraction.facts = [f for f in extraction.facts if f.field_name != question['id']]
        for extracted_fact in extraction.facts:
            safe_fact = extracted_fact.model_dump()
            try:
                safe_fact['value'] = validate_fact(safe_fact['field_name'], safe_fact['value'])
            except HTTPException:
                continue
            accepted = _write_fact(db, encounter_id, encounter["patient_id"], safe_fact)
            if accepted:
                extracted.append({"field_name": safe_fact["field_name"], "value": safe_fact["value"], "source": "AI_EXTRACTION", "confidence": safe_fact["confidence"]})
        updated_state = _state(db, encounter_id)
        # A newly reported danger must surface even if a contradictory old fact awaits review.
        observed = {f.field_name: f.value for f in extraction.facts}
        flags = red_flags(updated_state) + red_flags({**updated_state, **observed})
        _set_flags(db, encounter_id, flags, preserve=True)
        quality = completeness(updated_state, encounter["care_mode"])
        next_q = _planned_question(db, encounter, updated_state, refresh=True)
        next_status = "PATIENT_REVIEW" if next_q is None else "ACTIVE"
        next_stage = "PATIENT_REVIEW" if next_q is None else stage_for(updated_state, encounter["care_mode"])
        next_revision = encounter["revision"] + 1
        db.execute("UPDATE encounters SET status=?,stage=?,revision=?,ai_provider=? WHERE encounter_id=?", (next_status, next_stage, next_revision, provider, encounter_id))
        encounter.update({"status": next_status, "stage": next_stage, "revision": next_revision, "ai_provider": provider})
        store.audit(db, user.user_id, "INTERVIEW_ANSWER_RECORDED", "ENCOUNTER", encounter_id, {"question_id": question["id"], "provider": provider, "ai_latency_ms": interpretation.latency_ms})
        result = _response(db, encounter, extracted, ai_error)
    return _deliver_question(result)


@router.post("/{encounter_id}/voice")
async def voice_answer(
    encounter_id: str,
    file: UploadFile = File(...),
    expected_revision: int | None = Form(default=None, ge=0),
    user: AuthenticatedUser = Depends(current_user),
):
    """Transcribe real microphone audio locally, then run the normal validated intake path."""
    with store.connection() as db:
        row = db.execute("SELECT * FROM encounters WHERE encounter_id=?", (encounter_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Encounter not found")
        encounter = dict(row)
        assert_patient_access(db, user, encounter["patient_id"])
        if user.role != "PATIENT" or encounter["status"] != "ACTIVE":
            raise HTTPException(status_code=409, detail="This encounter is not accepting patient voice answers")
        if expected_revision is not None and expected_revision != encounter["revision"]:
            raise HTTPException(status_code=409, detail="This response is stale. Refresh the interview before continuing.")

    try:
        transcript = await transcribe_upload(file, encounter["language"])
    except SpeechToTextUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local speech recognition is unavailable. Check the configured Whisper model and try typing your answer.",
        ) from exc

    # Reuse the normal answer route so voice and typed answers have identical
    # validation, state transitions, clinical rules, and persistence behavior.
    response = await run_in_threadpool(answer, encounter_id, AnswerInput(message=transcript, expected_revision=encounter["revision"]), user)
    with store.connection() as db:
        store.audit(
            db,
            user.user_id,
            "VOICE_TRANSCRIBED",
            "ENCOUNTER",
            encounter_id,
            {"language": encounter["language"], "audio_bytes": getattr(file, "size", None), "engine": "faster_whisper"},
        )
    return {**response, "transcript": transcript, "stt_provider": "faster_whisper"}


@router.post("/{encounter_id}/transcribe")
async def transcribe_draft(encounter_id: str, file: UploadFile = File(...), expected_revision: int = Form(ge=0), user: AuthenticatedUser = Depends(current_user)):
    """Return a reviewable draft; never change facts, answers, or encounter revision."""
    with store.connection() as db:
        row = db.execute("SELECT * FROM encounters WHERE encounter_id=?", (encounter_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Encounter not found")
        assert_patient_access(db, user, row["patient_id"])
        if user.role != "PATIENT" or row["status"] != "ACTIVE":
            raise HTTPException(status_code=409, detail="This encounter is not accepting voice input")
        if row["revision"] != expected_revision:
            raise HTTPException(status_code=409, detail="The interview changed. Refresh before recording again.")
        language = row["language"]
    try:
        transcript = await transcribe_upload(file, language)
    except SpeechToTextUnavailable as exc:
        raise HTTPException(status_code=503, detail="Local speech recognition is unavailable. You can still type your answer.") from exc
    with store.connection() as db:
        store.audit(db, user.user_id, "VOICE_DRAFT_TRANSCRIBED", "ENCOUNTER", encounter_id, {"engine": "faster_whisper", "language": language})
    return {"transcript": transcript, "revision": expected_revision, "stt_provider": "faster_whisper", "saved_as_answer": False}


@router.post("/{encounter_id}/submit")
def submit(encounter_id: str, payload: SubmitInput, user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        row = db.execute("SELECT * FROM encounters WHERE encounter_id=?", (encounter_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Encounter not found")
        encounter = dict(row)
        assert_patient_access(db, user, encounter["patient_id"])
        if user.role != "PATIENT" or encounter["status"] not in {"ACTIVE", "PATIENT_REVIEW"}:
            raise HTTPException(status_code=409, detail="This encounter cannot be submitted by this user or in its current state")
        if not payload.reviewed:
            raise HTTPException(409, "Review your record and confirm consent before submission")
        state = _state(db, encounter_id)
        quality = completeness(state, encounter["care_mode"])
        answered = len(_answers(db, encounter_id))
        if answered < MIN_QUESTIONS:
            raise HTTPException(409, 'Complete at least five interview questions before submission')
        if quality["critical_missing"] and not budget(state, _answers(db, encounter_id), encounter['care_mode'])['complete']:
            raise HTTPException(status_code=409, detail={"message": "Critical intake information is still missing", "fields": quality["critical_missing"]})
        if payload.expected_revision is not None and payload.expected_revision != encounter["revision"]:
            raise HTTPException(status_code=409, detail="This submission is stale. Refresh the interview before continuing.")
        completed = now()
        db.execute("INSERT INTO consents(consent_id,patient_id,encounter_id,consent_type,version,purpose,status,recorded_by,recorded_at) VALUES(?,?,?,?,?,?,?,?,?)", (f"CON_{uuid4().hex}", encounter["patient_id"], encounter_id, "RECORD_SUBMISSION", "2026-09", "Share the patient-reviewed intake with authorized clinicians", "GRANTED", user.user_id, completed))
        store.audit(db, user.user_id, "PATIENT_REVIEW_CONFIRMED", "ENCOUNTER", encounter_id, {"revision": encounter["revision"], "consent_version": "2026-09"})
        db.execute("UPDATE encounters SET status='SUBMITTED',stage='RECONCILIATION',completed_at=?,revision=revision+1 WHERE encounter_id=?", (completed, encounter_id))
        db.execute(
            "INSERT INTO timeline_events(event_id,patient_id,encounter_id,event_type,title,detail,source,confidence,occurred_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (f"EVT_{uuid4().hex}", encounter["patient_id"], encounter_id, "ENCOUNTER_SUBMITTED", "Patient submitted intake for clinician review", factual_summary(state, quality, red_flags(state)), "PATIENT_REPORTED", 1.0, completed, completed),
        )
        store.audit(db, user.user_id, "ENCOUNTER_SUBMITTED", "ENCOUNTER", encounter_id)
        encounter.update({"status": "SUBMITTED", "stage": "RECONCILIATION", "completed_at": completed, "revision": encounter["revision"] + 1})
        return _response(db, encounter)


@router.get("/{encounter_id}")
def detail(encounter_id: str, user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        row = db.execute("SELECT * FROM encounters WHERE encounter_id=?", (encounter_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Encounter not found")
        encounter = dict(row)
        assert_patient_access(db, user, encounter["patient_id"])
        answers = [dict(answer) for answer in db.execute("SELECT * FROM answers WHERE encounter_id=? ORDER BY created_at", (encounter_id,)).fetchall()]
        store.audit(db, user.user_id, "ENCOUNTER_VIEWED", "ENCOUNTER", encounter_id)
        result = {**_response(db, encounter), "answers": answers}
    return _deliver_question(result)
