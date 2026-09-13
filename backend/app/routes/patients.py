from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

from backend.app.security import AuthenticatedUser, assert_patient_access, current_user
from backend.app.store import store

router = APIRouter(prefix="/patients", tags=["Patients"])


def patient_dto(row: dict) -> dict:
    return {
        "patient_id": row["patient_id"], "name": row["name"], "age": row["age"],
        "gender": row["gender"], "language": row["language"], "uhid": row.get("uhid"), "phone": row.get("phone"),
    }


@router.get("")
@router.get("/")
def list_patients(user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        if user.role == "PATIENT":
            rows = db.execute("SELECT * FROM patients WHERE patient_id=?", (user.patient_id,)).fetchall()
        elif user.role == "DOCTOR":
            rows = db.execute(
                "SELECT p.* FROM patients p JOIN clinician_assignments a ON a.patient_id=p.patient_id WHERE a.doctor_user_id=? ORDER BY p.updated_at DESC",
                (user.user_id,),
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM patients ORDER BY updated_at DESC").fetchall()
        store.audit(db, user.user_id, "PATIENT_LIST_VIEWED", "PATIENT_LIST", user.user_id)
        return [patient_dto(dict(row)) for row in rows]


@router.get("/{patient_id}")
def get_patient(patient_id: str, user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        assert_patient_access(db, user, patient_id)
        row = db.execute("SELECT * FROM patients WHERE patient_id=?", (patient_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Patient not found")
        store.audit(db, user.user_id, "PATIENT_RECORD_VIEWED", "PATIENT", patient_id)
        return patient_dto(dict(row))


@router.get("/{patient_id}/history")
def get_patient_history(patient_id: str, user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        assert_patient_access(db, user, patient_id)
        patient = db.execute("SELECT * FROM patients WHERE patient_id=?", (patient_id,)).fetchone()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        rows = db.execute(
            "SELECT field_name,value_json,source,confidence,status,created_at FROM clinical_facts WHERE patient_id=? AND superseded_at IS NULL ORDER BY created_at DESC",
            (patient_id,),
        ).fetchall()
        timeline = db.execute(
            "SELECT event_id,occurred_at,title,detail,source,confidence,event_type FROM timeline_events WHERE patient_id=? ORDER BY occurred_at ASC",
            (patient_id,),
        ).fetchall()
        store.audit(db, user.user_id, "PATIENT_HISTORY_VIEWED", "PATIENT", patient_id)
    facts = [{**dict(row), "value": json.loads(row["value_json"])} for row in rows]
    return {"patient": patient_dto(dict(patient)), "facts": facts, "timeline": [dict(row) for row in timeline]}
