from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.clinical_engine import ONTOLOGY, QUESTIONS, BOOL_FIELDS, runtime_ontology
from backend.app.security import AuthenticatedUser, require_roles
from backend.app.store import now, store

router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get('/providers')
def providers(user: AuthenticatedUser=Depends(require_roles('ADMIN'))):
    import os
    from backend.app.ai.providers import provider_manager
    return {'configured_provider':os.getenv('AI_PROVIDER','ollama'),'configured_model':os.getenv('AI_MODEL','qwen2.5:3b-instruct'),'providers':provider_manager.snapshot(),'external_ai_enabled':os.getenv('ALLOW_EXTERNAL_AI','false').lower()=='true','fallback':'clinical_rules'}


class OntologyRule(BaseModel):
    concept: str = Field(min_length=2, max_length=80)
    payload: dict
    enabled: bool = True


class RoleUpdate(BaseModel):
    role: Literal["PATIENT", "DOCTOR", "ADMIN"]


@router.get("/users")
def users(user: AuthenticatedUser = Depends(require_roles("ADMIN"))):
    with store.connection() as db:
        rows = [dict(row) for row in db.execute(
            "SELECT user_id,email,role,display_name,patient_id,created_at FROM users ORDER BY created_at DESC"
        ).fetchall()]
        store.audit(db, user.user_id, "USER_DIRECTORY_VIEWED", "USER_DIRECTORY", "global")
        return rows


@router.put("/users/{user_id}/role")
def update_role(user_id: str, payload: RoleUpdate, user: AuthenticatedUser = Depends(require_roles("ADMIN"))):
    if user_id == user.user_id and payload.role != "ADMIN":
        raise HTTPException(status_code=409, detail="An administrator cannot remove their own administrator role in this session")
    with store.connection() as db:
        target = db.execute("SELECT user_id,role FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        db.execute("UPDATE users SET role=? WHERE user_id=?", (payload.role, user_id))
        store.audit(db, user.user_id, "USER_ROLE_UPDATED", "USER", user_id, {"from": target["role"], "to": payload.role})
        return {"user_id": user_id, "role": payload.role}


@router.get("/audit-logs")
def audit_logs(user: AuthenticatedUser = Depends(require_roles("ADMIN"))):
    with store.connection() as db:
        rows = [dict(row) | {"metadata": json.loads(row["metadata_json"])} for row in db.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 500").fetchall()]
        store.audit(db, user.user_id, "AUDIT_LOG_VIEWED", "AUDIT_LOG", "global")
        return rows


@router.get("/ontology")
def ontology(user: AuthenticatedUser = Depends(require_roles("ADMIN"))):
    with store.connection() as db:
        custom = [dict(row) | {"payload": json.loads(row["payload_json"])} for row in db.execute("SELECT * FROM ontology_rules ORDER BY concept").fetchall()]
        store.audit(db, user.user_id, "ONTOLOGY_VIEWED", "ONTOLOGY", "global")
        return {"built_in": ONTOLOGY, "custom": custom}


@router.put("/ontology/{rule_id}")
def upsert_ontology(rule_id: str, payload: OntologyRule, user: AuthenticatedUser = Depends(require_roles("ADMIN"))):
    allowed_keys={'synonyms','required','body_system'}
    if set(payload.payload)-allowed_keys:
        raise HTTPException(422,'Ontology supports synonyms, required, and body_system only')
    for key in ('synonyms','required'):
        values=payload.payload.get(key,[])
        if not isinstance(values,list) or len(values)>50 or any(not isinstance(v,str) or not v.strip() or len(v)>100 for v in values):
            raise HTTPException(422,f'{key} must be a bounded list of non-empty strings')
    if any(field not in set(QUESTIONS)|BOOL_FIELDS for field in payload.payload.get('required',[])):
        raise HTTPException(422,'Each required field must have a supported clinical question')
    with store.connection() as db:
        db.execute(
            "INSERT INTO ontology_rules(rule_id,concept,payload_json,enabled,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(rule_id) DO UPDATE SET concept=excluded.concept,payload_json=excluded.payload_json,enabled=excluded.enabled,updated_at=excluded.updated_at",
            (rule_id, payload.concept, json.dumps(payload.payload, ensure_ascii=False), int(payload.enabled), now()),
        )
        store.audit(db, user.user_id, "ONTOLOGY_RULE_UPDATED", "ONTOLOGY_RULE", rule_id)
        db.commit()
        runtime_ontology.cache_clear()
        return {"rule_id": rule_id, "concept": payload.concept, "enabled": payload.enabled}


class AssignmentInput(BaseModel):
    doctor_user_id: str
    patient_id: str


@router.post('/assignments')
def assign(payload: AssignmentInput,user: AuthenticatedUser=Depends(require_roles('ADMIN'))):
    with store.connection() as db:
        if not db.execute("SELECT 1 FROM users WHERE user_id=? AND role='DOCTOR'",(payload.doctor_user_id,)).fetchone():
            raise HTTPException(422,'Select an existing doctor')
        if not db.execute('SELECT 1 FROM patients WHERE patient_id=?',(payload.patient_id,)).fetchone():
            raise HTTPException(404,'Patient not found')
        db.execute('INSERT OR IGNORE INTO clinician_assignments VALUES(?,?,?)',(payload.doctor_user_id,payload.patient_id,now()))
        store.audit(db,user.user_id,'CLINICIAN_ASSIGNED','PATIENT',payload.patient_id,{'doctor_user_id':payload.doctor_user_id})
    return {'assigned':True}
