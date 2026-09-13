"""Persisted, deterministic patient follow-up workflow.

Follow-up uses the finalized record as context, never invents a treatment plan,
and evaluates urgent symptoms with deterministic rules before any UI summary is
shown. It deliberately does not diagnose or change a medicine.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from backend.app.security import AuthenticatedUser, assert_patient_access, current_user, require_roles
from backend.app.store import now, store
from backend.app.voice import SpeechToTextUnavailable, transcribe_upload

router = APIRouter(prefix="/follow-ups", tags=["Patient Follow-up"])


class CreateFollowUpPlanInput(BaseModel):
    patient_id: str = Field(min_length=1, max_length=64)
    encounter_id: str = Field(min_length=1, max_length=80)
    instructions: str | None = Field(default=None, max_length=2000)
    follow_up_at: str | None = Field(default=None, max_length=40)


class FollowUpAnswerInput(BaseModel):
    question_id: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=4000)
    expected_revision: int = Field(ge=0)


RISK_RANK = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "EMERGENCY": 3}


def _record_state(db, encounter_id: str) -> dict[str, Any]:
    state: dict[str, Any] = {}
    for row in db.execute(
        """SELECT field_name,value_json FROM clinical_facts WHERE encounter_id=?
           AND superseded_at IS NULL AND status IN ('REPORTED','VERIFIED') ORDER BY created_at""",
        (encounter_id,),
    ):
        state[row["field_name"]] = json.loads(row["value_json"])
    return state


def _context(db, plan: dict[str, Any]) -> dict[str, Any]:
    encounter = dict(db.execute("SELECT * FROM encounters WHERE encounter_id=?", (plan["encounter_id"],)).fetchone())
    return {"encounter": encounter, "state": _record_state(db, plan["encounter_id"]), "instructions": plan.get("instructions") or ""}


def _questions(context: dict[str, Any]) -> list[dict[str, str]]:
    state = context["state"]
    complaint = str(state.get("chief_complaint") or "your symptoms")
    medications = state.get("medications") if isinstance(state.get("medications"), list) else []
    result = [
        {"id": "symptom_progress", "text": f"Since your last consultation for {complaint}, are your symptoms better, worse, or unchanged? Please describe what has changed."},
    ]
    if medications:
        result.append({"id": "medication_adherence", "text": "Are you taking your recorded medicines as prescribed? If not, which medicine is difficult and why?"})
        result.append({"id": "side_effects", "text": "Have you noticed any new problems or possible side effects after taking your recorded medicines?"})
    if context["instructions"]:
        result.append({"id": "plan_adherence", "text": "Have you been able to follow the doctor-recorded instructions for this visit?"})
    result.append({"id": "follow_up_appointment", "text": "Have you attended, scheduled, or need help arranging your next follow-up appointment?"})
    return result


def _responses(db, session_id: str) -> list[dict[str, Any]]:
    return [dict(row) for row in db.execute("SELECT * FROM follow_up_responses WHERE follow_up_session_id=? ORDER BY created_at", (session_id,))]


def _next_question(db, session: dict[str, Any], plan: dict[str, Any]) -> dict[str, str] | None:
    answered = {response["question_id"] for response in _responses(db, session["follow_up_session_id"])}
    return next((question for question in _questions(_context(db, plan)) if question["id"] not in answered), None)


def _follow_up_flags(message: str, state: dict[str, Any]) -> list[dict[str, Any]]:
    """Extensible deterministic safety layer; it never uses a language model."""
    text = message.casefold()
    flags: list[dict[str, Any]] = []
    breathless = any(term in text for term in ("short of breath", "breathless", "difficulty breathing", "cannot breathe", "सांस", "saans"))
    chest = any(term in text for term in ("chest pain", "chest discomfort", "chest pressure", "सीने में दर्द"))
    fainting = any(term in text for term in ("fainted", "fainting", "passed out", "बेहोश"))
    severe_bleeding = any(term in text for term in ("heavy bleeding", "vomiting blood", "blood in stool", "severe bleeding"))
    if (chest and breathless) or fainting or severe_bleeding:
        flags.append({"severity": "EMERGENCY", "message": "This follow-up response may need emergency assessment now. Do not wait for an online reply or the next routine visit.", "evidence": ["patient follow-up response"]})
    elif any(term in text for term in ("worse", "worsening", "getting worse", "severe pain", "high fever")):
        flags.append({"severity": "HIGH", "message": "The patient reports worsening or severe symptoms. A clinician should review this follow-up promptly.", "evidence": ["patient follow-up response"]})
    elif any(term in text for term in ("missed", "not taking", "cannot afford", "side effect", "side effects")):
        flags.append({"severity": "MODERATE", "message": "The patient reports a medication adherence or possible side-effect concern that needs clinician review.", "evidence": ["patient follow-up response"]})
    return flags


def _session_payload(db, plan: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
    context = _context(db, plan)
    alerts = [dict(row) | {"evidence": json.loads(row["evidence_json"])} for row in db.execute("SELECT * FROM follow_up_alerts WHERE follow_up_session_id=? ORDER BY created_at", (session["follow_up_session_id"],))]
    return {
        "plan": {key: plan[key] for key in ("follow_up_plan_id", "patient_id", "encounter_id", "instructions", "follow_up_at", "status", "created_at")},
        "session": session,
        "record_context": {"chief_complaint": context["state"].get("chief_complaint"), "medications": context["state"].get("medications", []), "allergies": context["state"].get("allergies", []), "doctor_instructions": context["instructions"]},
        "responses": _responses(db, session["follow_up_session_id"]),
        "next_question": _next_question(db, session, plan),
        "alerts": alerts,
    }


def create_follow_up_plan(db, *, patient_id: str, encounter_id: str, created_by: str, instructions: str | None = None, follow_up_at: str | None = None) -> dict[str, Any]:
    """Create exactly one plan for a finalized encounter, without invented advice."""
    existing = db.execute("SELECT * FROM follow_up_plans WHERE encounter_id=?", (encounter_id,)).fetchone()
    if existing:
        return dict(existing)
    plan = {
        "follow_up_plan_id": f"FUP_{uuid4().hex}",
        "patient_id": patient_id,
        "encounter_id": encounter_id,
        "instructions": instructions.strip() if instructions else None,
        "follow_up_at": follow_up_at,
        "status": "ACTIVE",
        "created_by": created_by,
        "created_at": now(),
        "updated_at": now(),
    }
    db.execute(
        """INSERT INTO follow_up_plans(follow_up_plan_id,patient_id,encounter_id,instructions,follow_up_at,status,created_by,created_at,updated_at)
           VALUES(:follow_up_plan_id,:patient_id,:encounter_id,:instructions,:follow_up_at,:status,:created_by,:created_at,:updated_at)""",
        plan,
    )
    db.execute(
        """INSERT INTO timeline_events(event_id,patient_id,encounter_id,event_type,title,detail,source,confidence,occurred_at,created_at,verification_status,metadata_json)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (f"EVT_{uuid4().hex}", patient_id, encounter_id, "FOLLOW_UP_PLAN_CREATED", "Follow-up plan created", "A clinician finalized the encounter and enabled a patient follow-up check-in.", "DOCTOR_ENTERED", 1.0, plan["created_at"], plan["created_at"], "VERIFIED", json.dumps({"follow_up_plan_id": plan["follow_up_plan_id"]})),
    )
    store.audit(db, created_by, "FOLLOW_UP_PLAN_CREATED", "FOLLOW_UP_PLAN", plan["follow_up_plan_id"], {"encounter_id": encounter_id})
    return plan


@router.post("/plans", status_code=status.HTTP_201_CREATED)
def create_plan(payload: CreateFollowUpPlanInput, user: AuthenticatedUser = Depends(require_roles("DOCTOR", "ADMIN"))):
    with store.connection() as db:
        encounter = db.execute("SELECT * FROM encounters WHERE encounter_id=? AND patient_id=?", (payload.encounter_id, payload.patient_id)).fetchone()
        if not encounter:
            raise HTTPException(status_code=404, detail="Finalized encounter not found")
        assert_patient_access(db, user, payload.patient_id)
        if encounter["status"] != "FINALIZED":
            raise HTTPException(status_code=409, detail="Follow-up starts after clinician finalization")
        plan = create_follow_up_plan(db, patient_id=payload.patient_id, encounter_id=payload.encounter_id, created_by=user.user_id, instructions=payload.instructions, follow_up_at=payload.follow_up_at)
        return plan


@router.get("/patients/{patient_id}")
def patient_follow_up(patient_id: str, user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        assert_patient_access(db, user, patient_id)
        plans = [dict(row) for row in db.execute("SELECT * FROM follow_up_plans WHERE patient_id=? ORDER BY created_at DESC", (patient_id,))]
        result = []
        for plan in plans:
            sessions = [dict(row) for row in db.execute("SELECT * FROM follow_up_sessions WHERE follow_up_plan_id=? ORDER BY started_at DESC", (plan["follow_up_plan_id"],))]
            alerts = [dict(row) for row in db.execute("SELECT a.* FROM follow_up_alerts a JOIN follow_up_sessions s ON s.follow_up_session_id=a.follow_up_session_id WHERE s.follow_up_plan_id=? ORDER BY a.created_at DESC", (plan["follow_up_plan_id"],))]
            result.append({"plan": plan, "sessions": sessions, "alerts": alerts, "last_check_in": sessions[0] if sessions else None})
        store.audit(db, user.user_id, "FOLLOW_UP_VIEWED", "PATIENT", patient_id)
        return result


@router.post("/plans/{plan_id}/sessions", status_code=status.HTTP_201_CREATED)
def start_session(plan_id: str, user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        row = db.execute("SELECT * FROM follow_up_plans WHERE follow_up_plan_id=?", (plan_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Follow-up plan not found")
        plan = dict(row)
        assert_patient_access(db, user, plan["patient_id"])
        if user.role != "PATIENT" or plan["status"] != "ACTIVE":
            raise HTTPException(status_code=409, detail="This follow-up plan is not available for patient check-in")
        active = db.execute("SELECT * FROM follow_up_sessions WHERE follow_up_plan_id=? AND status='ACTIVE' ORDER BY started_at DESC LIMIT 1", (plan_id,)).fetchone()
        if active:
            response = _session_payload(db, plan, dict(active))
            response["resumed"] = True
            return response
        session = {"follow_up_session_id": f"FUS_{uuid4().hex}", "follow_up_plan_id": plan_id, "patient_id": plan["patient_id"], "status": "ACTIVE", "revision": 0, "risk_level": "LOW", "started_at": now(), "completed_at": None}
        db.execute(
            """INSERT INTO follow_up_sessions(follow_up_session_id,follow_up_plan_id,patient_id,status,revision,risk_level,started_at,completed_at)
               VALUES(:follow_up_session_id,:follow_up_plan_id,:patient_id,:status,:revision,:risk_level,:started_at,:completed_at)""",
            session,
        )
        store.audit(db, user.user_id, "FOLLOW_UP_STARTED", "FOLLOW_UP_SESSION", session["follow_up_session_id"])
        return _session_payload(db, plan, session)


@router.post("/sessions/{session_id}/answers")
def answer(session_id: str, payload: FollowUpAnswerInput, user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        row = db.execute("SELECT * FROM follow_up_sessions WHERE follow_up_session_id=?", (session_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Follow-up session not found")
        session = dict(row)
        assert_patient_access(db, user, session["patient_id"])
        if user.role != "PATIENT" or session["status"] != "ACTIVE":
            raise HTTPException(status_code=409, detail="This follow-up session is not accepting responses")
        if session["revision"] != payload.expected_revision:
            raise HTTPException(status_code=409, detail="This check-in changed. Reload before submitting the response.")
        plan = dict(db.execute("SELECT * FROM follow_up_plans WHERE follow_up_plan_id=?", (session["follow_up_plan_id"],)).fetchone())
        question = _next_question(db, session, plan)
        if not question or question["id"] != payload.question_id:
            raise HTTPException(status_code=409, detail="The response does not match the current follow-up question")
        message = payload.message.strip()
        db.execute(
            """INSERT INTO follow_up_responses(follow_up_response_id,follow_up_session_id,question_id,question_text,response_text,source,created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (f"FUR_{uuid4().hex}", session_id, question["id"], question["text"], message, "PATIENT_REPORTED", now()),
        )
        context = _context(db, plan)
        flags = _follow_up_flags(message, context["state"])
        highest = session["risk_level"]
        for flag in flags:
            if RISK_RANK[flag["severity"]] > RISK_RANK[highest]:
                highest = flag["severity"]
            duplicate = db.execute("SELECT 1 FROM follow_up_alerts WHERE follow_up_session_id=? AND message=?", (session_id, flag["message"])).fetchone()
            if not duplicate:
                db.execute(
                    """INSERT INTO follow_up_alerts(follow_up_alert_id,follow_up_session_id,severity,message,evidence_json,status,created_at)
                       VALUES(?,?,?,?,?,?,?)""",
                    (f"FUA_{uuid4().hex}", session_id, flag["severity"], flag["message"], json.dumps(flag["evidence"]), "OPEN", now()),
                )
        revised = session["revision"] + 1
        db.execute("UPDATE follow_up_sessions SET revision=?,risk_level=? WHERE follow_up_session_id=?", (revised, highest, session_id))
        db.execute(
            """INSERT INTO timeline_events(event_id,patient_id,encounter_id,event_type,title,detail,source,confidence,occurred_at,created_at,verification_status,metadata_json)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (f"EVT_{uuid4().hex}", session["patient_id"], plan["encounter_id"], "FOLLOW_UP_RESPONSE", f"Follow-up: {question['id'].replace('_', ' ')}", message[:1000], "PATIENT_REPORTED", 1.0, now(), now(), "REPORTED", json.dumps({"follow_up_session_id": session_id, "question_id": question["id"], "risk_level": highest})),
        )
        refreshed = dict(db.execute("SELECT * FROM follow_up_sessions WHERE follow_up_session_id=?", (session_id,)).fetchone())
        if _next_question(db, refreshed, plan) is None:
            db.execute("UPDATE follow_up_sessions SET status='COMPLETED',completed_at=? WHERE follow_up_session_id=?", (now(), session_id))
            refreshed = dict(db.execute("SELECT * FROM follow_up_sessions WHERE follow_up_session_id=?", (session_id,)).fetchone())
        store.audit(db, user.user_id, "FOLLOW_UP_RESPONSE_RECORDED", "FOLLOW_UP_SESSION", session_id, {"question_id": question["id"], "risk_level": highest})
        return _session_payload(db, plan, refreshed)


@router.post("/sessions/{session_id}/transcribe")
async def transcribe(session_id: str, file: UploadFile = File(...), expected_revision: int = Form(...), user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        row = db.execute("SELECT * FROM follow_up_sessions WHERE follow_up_session_id=?", (session_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Follow-up session not found")
        session = dict(row)
        assert_patient_access(db, user, session["patient_id"])
        if user.role != "PATIENT" or session["status"] != "ACTIVE" or session["revision"] != expected_revision:
            raise HTTPException(status_code=409, detail="This follow-up session changed. Reload before recording.")
        plan = dict(db.execute("SELECT * FROM follow_up_plans WHERE follow_up_plan_id=?", (session["follow_up_plan_id"],)).fetchone())
        language = db.execute("SELECT language FROM encounters WHERE encounter_id=?", (plan["encounter_id"],)).fetchone()["language"]
    try:
        transcript = await transcribe_upload(file, language)
    except SpeechToTextUnavailable as exc:
        raise HTTPException(status_code=503, detail="Local transcription is unavailable. Type your response instead.") from exc
    return {"transcript": transcript, "saved_as_answer": False, "revision": expected_revision}


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge(alert_id: str, user: AuthenticatedUser = Depends(require_roles("DOCTOR", "ADMIN"))):
    with store.connection() as db:
        row = db.execute("SELECT a.*,s.patient_id FROM follow_up_alerts a JOIN follow_up_sessions s ON s.follow_up_session_id=a.follow_up_session_id WHERE a.follow_up_alert_id=?", (alert_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Follow-up alert not found")
        assert_patient_access(db, user, row["patient_id"])
        if row["status"] != "OPEN":
            raise HTTPException(status_code=409, detail="This alert has already been handled")
        db.execute("UPDATE follow_up_alerts SET status='ACKNOWLEDGED',resolved_at=?,resolved_by=? WHERE follow_up_alert_id=?", (now(), user.user_id, alert_id))
        store.audit(db, user.user_id, "FOLLOW_UP_ALERT_ACKNOWLEDGED", "FOLLOW_UP_ALERT", alert_id)
        return {"follow_up_alert_id": alert_id, "status": "ACKNOWLEDGED"}
