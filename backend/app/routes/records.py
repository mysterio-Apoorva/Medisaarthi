"""Encounter observations, clinician prescriptions and finalized A4 records."""
from __future__ import annotations

import json
import logging
import math
from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.security import AuthenticatedUser, assert_patient_access, current_user, require_roles
from backend.app.store import now, store

router = APIRouter(prefix='/records', tags=['Clinical records'])
logger = logging.getLogger(__name__)

# Units are input contracts, not reference ranges or diagnostic thresholds.
VITAL_UNITS = {
    'systolic blood pressure': {'mmHg'}, 'diastolic blood pressure': {'mmHg'},
    'pulse': {'beats/min', 'bpm'}, 'heart rate': {'beats/min', 'bpm'},
    'temperature': {'C', 'F', '°C', '°F'}, 'spo2': {'%'}, 'spo₂': {'%'},
    'weight': {'kg'}, 'height': {'cm', 'm'}, 'bmi': {'kg/m2', 'kg/m²'},
}


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, allow_inf_nan=False)


class ObservationInput(Input):
    kind: Literal['VITAL', 'TEST']
    name: str = Field(min_length=1, max_length=120)
    value: float = Field(ge=-1e9, le=1e9)
    unit: str = Field(min_length=1, max_length=40)
    measured_at: datetime
    request_id: UUID

    @model_validator(mode='after')
    def valid_measurement(self):
        if self.measured_at.tzinfo is None or self.measured_at > datetime.now(timezone.utc):
            raise ValueError('Measurement time must include a timezone and cannot be in the future')
        if self.kind == 'VITAL' and self.value <= 0:
            raise ValueError('Vital readings must be positive')
        if self.unit == '%' and not 0 <= self.value <= 100:
            raise ValueError('Percent values must be between 0 and 100')
        units = VITAL_UNITS.get(self.name.casefold()) if self.kind == 'VITAL' else None
        if units and self.unit not in units:
            raise ValueError('Use one of these units for this vital: ' + ', '.join(sorted(units)))
        self.measured_at = self.measured_at.astimezone(timezone.utc)
        return self


class VoidInput(Input):
    reason: str = Field(min_length=3, max_length=500)


class Medicine(Input):
    name: str = Field(min_length=1, max_length=160)
    strength: str = Field(min_length=1, max_length=100)
    dose: str = Field(min_length=1, max_length=100)
    frequency: str = Field(min_length=1, max_length=100)
    duration: str = Field(min_length=1, max_length=100)
    route: str = Field(min_length=1, max_length=80)
    instructions: str = Field(min_length=1, max_length=1000)


class PrescriptionInput(Input):
    expected_revision: int = Field(ge=0)
    medicines: list[Medicine] = Field(max_length=50)
    advice: str = Field(min_length=1, max_length=6000)
    no_medicines_reason: str | None = Field(default=None, min_length=3, max_length=1000)
    follow_up_at: date | None = None
    allergies_reviewed: bool = False
    allergy_review: list[str] | None = Field(default=None, max_length=50)

    @model_validator(mode='after')
    def complete_plan(self):
        if not self.medicines and not self.no_medicines_reason:
            raise ValueError('Record medicines or explain why no medicines are prescribed')
        names = [medicine.name.casefold() for medicine in self.medicines]
        if len(set(names)) != len(names):
            raise ValueError('Duplicate medicines: combine the instructions into one entry')
        return self


def recorded_allergies(db, encounter_id):
    row = db.execute("SELECT value_json FROM clinical_facts WHERE encounter_id=? AND field_name='allergies' AND superseded_at IS NULL AND status IN ('REPORTED','VERIFIED') ORDER BY created_at DESC LIMIT 1", (encounter_id,)).fetchone()
    return json.loads(row['value_json']) if row else None


def encounter_access(db, encounter_id: str, user: AuthenticatedUser, *, write=False):
    row = db.execute('SELECT * FROM encounters WHERE encounter_id=?', (encounter_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Encounter not found')
    assert_patient_access(db, user, row['patient_id'])
    if write and row['status'] == 'FINALIZED':
        raise HTTPException(409, 'The finalized clinical record cannot be changed')
    return dict(row)


def prescription_record(db, encounter_id):
    row = db.execute('SELECT p.*,u.display_name AS doctor_name FROM prescriptions p JOIN users u ON u.user_id=p.doctor_user_id WHERE encounter_id=?', (encounter_id,)).fetchone()
    if not row:
        return None
    result = dict(row)
    result['medicines'] = json.loads(result.pop('medicines_json'))
    result['allergy_review'] = json.loads(result.pop('allergy_review_json') or 'null')
    return result


def event(db, encounter, user, action, detail, resource_id):
    timestamp = now()
    db.execute('INSERT INTO timeline_events(event_id,patient_id,encounter_id,event_type,title,detail,source,confidence,occurred_at,created_at,verification_status,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
               (f'EVT_{uuid4().hex}', encounter['patient_id'], encounter['encounter_id'], action, action.replace('_', ' ').title(), detail,
                'PATIENT_REPORTED' if user.role == 'PATIENT' else 'DOCTOR_ENTERED', 1.0, timestamp, timestamp,
                'REPORTED' if user.role == 'PATIENT' else 'VERIFIED', json.dumps({'resource_id': resource_id})))
    store.audit(db, user.user_id, action, 'ENCOUNTER', encounter['encounter_id'], {'resource_id': resource_id})


def _refresh_bmi(db, encounter, user):
    """Persist a calculation from the latest retained height/weight and link its inputs."""
    rows = [dict(r) for r in db.execute("SELECT * FROM observations WHERE encounter_id=? AND kind='VITAL' AND voided_at IS NULL ORDER BY measured_at DESC,created_at DESC", (encounter['encounter_id'],))]
    weight = next((r for r in rows if r['name'].casefold() == 'weight' and r['unit'] == 'kg'), None)
    height = next((r for r in rows if r['name'].casefold() == 'height' and r['unit'] in {'cm', 'm'}), None)
    inputs = [weight['observation_id'], height['observation_id']] if weight and height else []
    active = next((r for r in rows if r['source'] == 'CALCULATED' and r['name'] == 'BMI'), None)
    if active and json.loads(active['metadata_json']).get('input_observation_ids') == inputs:
        return
    if active:
        db.execute('UPDATE observations SET voided_at=?,void_reason=? WHERE observation_id=?', (now(), 'Source height or weight changed or was withdrawn', active['observation_id']))
        event(db, encounter, user, 'OBSERVATION_WITHDRAWN', 'Calculated BMI superseded because its source measurements changed', active['observation_id'])
    if not weight or not height:
        return
    metres = height['value'] / 100 if height['unit'] == 'cm' else height['value']
    if metres <= 0 or weight['value'] <= 0:
        return
    # https://www.cdc.gov/growth-chart-training/hcp/using-bmi/calculating-bmi.html
    try:
        value = round(weight['value'] / metres ** 2, 2)
    except (ZeroDivisionError, OverflowError):
        raise HTTPException(422, 'Height and weight cannot produce a finite BMI')
    if not math.isfinite(value):
        raise HTTPException(422, 'Height and weight cannot produce a finite BMI')
    oid = f'OBS_{uuid4().hex}'
    measured_at = max(weight['measured_at'], height['measured_at'])
    metadata = {'input_observation_ids': inputs, 'formula': 'weight_kg / height_m^2', 'weight_kg': weight['value'], 'height_m': metres,
                'weight_measured_at': weight['measured_at'], 'height_measured_at': height['measured_at']}
    db.execute('INSERT INTO observations(observation_id,encounter_id,kind,name,value,unit,measured_at,source,recorded_by,created_at,request_id,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
               (oid, encounter['encounter_id'], 'VITAL', 'BMI', value, 'kg/m2', measured_at, 'CALCULATED', user.user_id, now(), str(uuid4()), json.dumps(metadata)))
    event(db, encounter, user, 'OBSERVATION_RECORDED', f'BMI: {value} kg/m2; calculated from weight {weight["value"]} kg and height {metres} m; source readings {", ".join(inputs)}', oid)


@router.get('/{encounter_id}')
def read_record(encounter_id: str, user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        encounter = encounter_access(db, encounter_id, user)
        return {'encounter_id': encounter_id, 'status': encounter['status'],
                'observations': [dict(row) for row in db.execute('SELECT * FROM observations WHERE encounter_id=? ORDER BY measured_at', (encounter_id,))],
                'prescription': prescription_record(db, encounter_id),
                'allergies': recorded_allergies(db, encounter_id),
                'pdf_available': bool(db.execute('SELECT 1 FROM finalized_records WHERE encounter_id=?', (encounter_id,)).fetchone())}


@router.post('/{encounter_id}/observations', status_code=201)
def add_observation(encounter_id: str, payload: ObservationInput, user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        encounter = encounter_access(db, encounter_id, user, write=True)
        if user.role == 'PATIENT' and encounter['status'] not in {'ACTIVE', 'PATIENT_REVIEW'}:
            raise HTTPException(409, 'Patient measurements must be recorded before submission')
        existing = db.execute('SELECT * FROM observations WHERE encounter_id=? AND request_id=?', (encounter_id, str(payload.request_id))).fetchone()
        if existing:
            if any(existing[key] != getattr(payload, key) for key in ('kind', 'name', 'value', 'unit')) or existing['measured_at'] != payload.measured_at.isoformat():
                raise HTTPException(409, 'This request ID already belongs to a different measurement')
            return dict(existing)
        if db.execute('SELECT 1 FROM observations WHERE encounter_id=? AND kind=? AND lower(trim(name))=lower(?) AND value=? AND unit=? AND measured_at=? AND voided_at IS NULL',
                      (encounter_id, payload.kind, payload.name, payload.value, payload.unit, payload.measured_at.isoformat())).fetchone():
            raise HTTPException(409, 'This measurement is already recorded for this time')
        oid = f'OBS_{uuid4().hex}'
        db.execute('INSERT INTO observations(observation_id,encounter_id,kind,name,value,unit,measured_at,source,recorded_by,created_at,request_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                   (oid, encounter_id, payload.kind, payload.name, payload.value, payload.unit, payload.measured_at.isoformat(), 'PATIENT_MANUAL' if user.role == 'PATIENT' else 'CLINICIAN_MANUAL', user.user_id, now(), str(payload.request_id)))
        db.execute('UPDATE encounters SET revision=revision+1 WHERE encounter_id=?', (encounter_id,))
        event(db, encounter, user, 'OBSERVATION_RECORDED', f'{payload.name}: {payload.value} {payload.unit}; measured {payload.measured_at.isoformat()}', oid)
        if payload.kind == 'VITAL' and payload.name.casefold() in {'height', 'weight'}:
            _refresh_bmi(db, encounter, user)
        return dict(db.execute('SELECT * FROM observations WHERE observation_id=?', (oid,)).fetchone())


@router.post('/{encounter_id}/observations/{observation_id}/void')
def void_observation(encounter_id: str, observation_id: str, payload: VoidInput, user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        encounter = encounter_access(db, encounter_id, user, write=True)
        row = db.execute('SELECT * FROM observations WHERE observation_id=? AND encounter_id=?', (observation_id, encounter_id)).fetchone()
        if not row:
            raise HTTPException(404, 'Observation not found')
        if user.role == 'PATIENT' and (row['recorded_by'] != user.user_id or encounter['status'] not in {'ACTIVE', 'PATIENT_REVIEW'}):
            raise HTTPException(403, 'Only your own unsubmitted readings can be withdrawn')
        if row['voided_at']:
            raise HTTPException(409, 'This reading is already withdrawn')
        if row['source'] == 'CALCULATED':
            raise HTTPException(409, 'Withdraw or correct the source height or weight to update calculated BMI')
        db.execute('UPDATE observations SET voided_at=?,void_reason=? WHERE observation_id=?', (now(), payload.reason, observation_id))
        db.execute('UPDATE encounters SET revision=revision+1 WHERE encounter_id=?', (encounter_id,))
        event(db, encounter, user, 'OBSERVATION_WITHDRAWN', payload.reason, observation_id)
        if row['kind'] == 'VITAL' and row['name'].casefold() in {'height', 'weight'}:
            _refresh_bmi(db, encounter, user)
        return dict(db.execute('SELECT * FROM observations WHERE observation_id=?', (observation_id,)).fetchone())


@router.put('/{encounter_id}/prescription')
def save_prescription(encounter_id: str, payload: PrescriptionInput, user: AuthenticatedUser = Depends(require_roles('DOCTOR'))):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        encounter = encounter_access(db, encounter_id, user, write=True)
        if encounter['status'] != 'SUBMITTED':
            raise HTTPException(409, 'The patient must submit the encounter before prescribing')
        existing = prescription_record(db, encounter_id)
        revision = existing['revision'] if existing else 0
        if revision != payload.expected_revision:
            raise HTTPException(409, 'The prescription changed. Reload before saving')
        allergies = recorded_allergies(db, encounter_id)
        if payload.medicines and not payload.allergies_reviewed:
            raise HTTPException(422, 'Review the recorded allergy information before prescribing')
        if payload.medicines and payload.allergy_review != allergies:
            raise HTTPException(409, 'Allergy information changed. Reload and review it before prescribing')
        review = {'allergies': allergies, 'reviewed_by': user.user_id, 'reviewed_at': now()} if payload.medicines else None
        db.execute('INSERT INTO prescriptions(encounter_id,revision,medicines_json,advice,no_medicines_reason,follow_up_at,doctor_user_id,updated_at,allergy_review_json) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(encounter_id) DO UPDATE SET revision=excluded.revision,medicines_json=excluded.medicines_json,advice=excluded.advice,no_medicines_reason=excluded.no_medicines_reason,follow_up_at=excluded.follow_up_at,doctor_user_id=excluded.doctor_user_id,updated_at=excluded.updated_at,allergy_review_json=excluded.allergy_review_json',
                   (encounter_id, revision + 1, json.dumps([m.model_dump() for m in payload.medicines]), payload.advice, payload.no_medicines_reason, payload.follow_up_at.isoformat() if payload.follow_up_at else None, user.user_id, now(), json.dumps(review)))
        db.execute('UPDATE encounters SET revision=revision+1 WHERE encounter_id=?', (encounter_id,))
        event(db, encounter, user, 'PRESCRIPTION_SAVED', payload.advice, encounter_id)
        return prescription_record(db, encounter_id)


def snapshot_record(db, encounter_id, user):
    """Called in the finalization transaction; the PDF and follow-up share this record."""
    encounter = dict(db.execute('SELECT * FROM encounters WHERE encounter_id=?', (encounter_id,)).fetchone())
    patient = dict(db.execute('SELECT * FROM patients WHERE patient_id=?', (encounter['patient_id'],)).fetchone())
    tables = ('clinical_facts', 'answers', 'documents', 'observations', 'reconciliation_items', 'timeline_events', 'red_flags')
    snapshot = {'patient': patient, 'encounter': encounter, 'prescription': prescription_record(db, encounter_id), 'finalized_by': user.display_name}
    for table in tables:
        snapshot[table] = [dict(row) for row in db.execute(f'SELECT * FROM {table} WHERE encounter_id=?', (encounter_id,))]
    snapshot['document_entities'] = [dict(row) for row in db.execute('SELECT e.* FROM document_entities e JOIN documents d ON d.document_id=e.document_id WHERE d.encounter_id=?', (encounter_id,))]
    db.execute('INSERT INTO finalized_records VALUES(?,?,?,?)', (encounter_id, json.dumps(snapshot, ensure_ascii=False), user.user_id, encounter['finalized_at']))


@router.get('/{encounter_id}/pdf')
def get_pdf(encounter_id: str, user: AuthenticatedUser = Depends(current_user)):
    with store.connection() as db:
        encounter_access(db, encounter_id, user)
        row = db.execute('SELECT snapshot_json FROM finalized_records WHERE encounter_id=?', (encounter_id,)).fetchone()
        if not row:
            raise HTTPException(409, 'A clinician must finalize the complete record before generating its PDF')
        snapshot = json.loads(row['snapshot_json'])
    try:
        from backend.app.pdf_service import render_record
        content = render_record(snapshot)
    except Exception as exc:
        logger.exception('pdf_generation_failed encounter=%s', encounter_id)
        raise HTTPException(503, 'Unable to generate the medical record PDF. Please retry.') from exc
    with store.connection() as db:
        store.audit(db, user.user_id, 'PDF_GENERATED', 'ENCOUNTER', encounter_id)
    return Response(content, media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="{encounter_id}.pdf"'})
