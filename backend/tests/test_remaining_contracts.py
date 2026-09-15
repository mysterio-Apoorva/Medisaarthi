"""Endpoint-specific success, validation, lifecycle and relational checks."""
import sqlite3
import json
from uuid import uuid4

import pymupdf
import pytest

from backend.app.store import store
from backend.tests.test_clinical_records import client, login, plan, ENCOUNTER
from backend.tests.test_current_system import _new_encounter


def test_directory_admin_and_assignment_contracts(client):
    assert client.get('/').status_code == 200
    assert client.get('/auth/me').json()['user']['role'] == 'DOCTOR'
    for path in ['/patients', '/patients/', '/patients/P1001/history', '/doctor/patients/P1001/summary', '/doctor/patients/P1001/timeline', '/doctor/patients/P1001/audit', f'/doctor/encounters/{ENCOUNTER}/reconciliation']:
        assert client.get(path).status_code == 200, path
    login(client, 'admin')
    for path in ['/admin/users', '/admin/providers', '/admin/audit-logs', '/admin/ontology', '/knowledge/references']:
        assert client.get(path).status_code == 200, path
    assert client.get('/admin/providers').json()['fallback'] is None
    assert client.put('/admin/users/missing/role', json={'role': 'DOCTOR'}).status_code == 404
    assert client.put('/admin/users/USR_ADMIN_DEMO/role', json={'role': 'PATIENT'}).status_code == 409
    assert client.put('/admin/users/USR_DOCTOR_DEMO/role', json={'role': 'DOCTOR'}).status_code == 200
    assert client.put('/admin/users/USR_DOCTOR_DEMO/role', json={'role': 'invalid'}).status_code == 422
    assert client.post('/admin/assignments', json={'doctor_user_id': 'missing', 'patient_id': 'P1001'}).status_code == 422
    assert client.post('/admin/assignments', json={'doctor_user_id': 'USR_DOCTOR_DEMO', 'patient_id': 'missing'}).status_code == 404
    assignment = {'doctor_user_id': 'USR_DOCTOR_DEMO', 'patient_id': 'P1001'}
    assert client.post('/admin/assignments', json=assignment).json()['assigned'] is True
    assert client.post('/admin/assignments', json=assignment).status_code == 200
    with store.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM clinician_assignments WHERE doctor_user_id=? AND patient_id=?', tuple(assignment.values())).fetchone()[0] == 1


def document_bytes(text='Tablet Synthetic medication 1 unit'):
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), text)
        return document.tobytes()


def test_document_retry_duplicate_delete_and_reconciliation(client):
    started = _new_encounter(client)
    encounter = started['encounter_id']
    assert client.post('/interviews/consents', json={'patient_id': 'P1001', 'consent_type': 'DOCUMENT_PROCESSING'}).status_code == 201
    upload = {'file': ('test.pdf', document_bytes(), 'application/pdf')}
    response = client.post(f'/documents/encounters/{encounter}', files=upload)
    assert response.status_code == 201, response.text
    identifier = response.json()['document_id']
    assert client.post(f'/documents/encounters/{encounter}', files=upload).status_code == 409
    assert client.get(f'/documents/encounters/{encounter}').json()[0]['document_id'] == identifier
    assert client.get(f'/documents/encounters/{encounter}').json()[0]['can_retry'] is True
    assert client.post(f'/documents/{identifier}/retry').status_code == 200
    assert client.get(f'/documents/{identifier}/file').content.startswith(b'%PDF')
    assert client.delete(f'/documents/{identifier}').status_code == 204
    assert client.get(f'/documents/{identifier}/file').status_code == 404
    with store.connection() as db:
        for table in ['document_pages', 'document_entities', 'reconciliation_items', 'timeline_events']:
            assert db.execute(f'SELECT COUNT(*) FROM {table} WHERE document_id=?', (identifier,)).fetchone()[0] == 0
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    response = client.post(f'/documents/encounters/{encounter}', files=upload)
    identifier = response.json()['document_id']
    login(client, 'doctor')
    items = client.get(f'/doctor/encounters/{encounter}/reconciliation').json()
    assert items
    item = items[0]['reconciliation_id']
    assert client.post(f'/doctor/reconciliation/{item}', json={'action': 'MERGED'}).status_code == 422
    assert client.post(f'/doctor/reconciliation/{item}', json={'action': 'APPROVED'}).status_code == 200
    timeline = client.get('/doctor/patients/P1001/timeline').json()
    assert any(row['document_id'] == identifier and row['event_type'] == 'DOCUMENT_MEDICATION' and row['verification_status'] == 'VERIFIED' for row in timeline)
    assert any(row['event_type'] == 'RECONCILIATION_RESOLVED' and json.loads(row['metadata_json'])['reconciliation_id'] == item for row in timeline)
    assert any(row['resource_id'] == item and row['action'] == 'RECONCILIATION_RESOLVED' for row in client.get('/doctor/patients/P1001/audit').json())
    assert client.post(f'/doctor/reconciliation/{item}', json={'action': 'REJECTED'}).status_code == 409
    assert client.post(f'/documents/{identifier}/retry').status_code == 409
    listed = client.get(f'/documents/encounters/{encounter}').json()[0]
    assert listed['can_retry'] is False and listed['can_remove'] is False
    login(client, 'patient')
    assert client.delete(f'/documents/{identifier}').status_code == 409


def test_clinician_correction_and_follow_up_contracts(client):
    correction = client.post('/doctor/patients/P1001/facts', json={'field_name': 'duration', 'value': 'two days', 'reason': 'Synthetic clinician correction'})
    assert correction.status_code == 200, correction.text
    assert client.get('/doctor/patients/P1001/summary').json()['clinical_state']['duration'] == 'two days'
    assert client.post('/doctor/patients/P1001/facts', json={'field_name': 'severity', 'value': 11}).status_code == 422
    assert client.put(f'/records/{ENCOUNTER}/prescription', json=plan()).status_code == 200
    finalized = client.post(f'/doctor/encounters/{ENCOUNTER}/finalize').json()
    plan_id = finalized['follow_up_plan_id']
    assert client.post('/follow-ups/plans', json={'patient_id': 'P1001', 'encounter_id': ENCOUNTER, 'instructions': 'Synthetic follow-up instructions'}).status_code == 201
    login(client, 'patient')
    assert client.get('/follow-ups/patients/P1001').json()
    session = client.post(f'/follow-ups/plans/{plan_id}/sessions').json()
    identifier = session['session']['follow_up_session_id']
    response = client.post(f'/follow-ups/sessions/{identifier}/answers', json={'question_id': session['next_question']['id'], 'message': 'My symptoms are getting worse', 'expected_revision': 0})
    assert response.status_code == 200, response.text
    alert = response.json()['alerts'][0]['follow_up_alert_id']
    login(client, 'doctor')
    assert client.post(f'/follow-ups/alerts/{alert}/acknowledge').status_code == 200
    assert client.post('/follow-ups/alerts/missing/acknowledge').status_code == 404


def test_database_transactions_foreign_keys_and_finalized_immutability(client):
    identifier = 'USR_' + uuid4().hex
    with pytest.raises(RuntimeError):
        with store.connection() as db:
            db.execute('INSERT INTO users(user_id,email,password_hash,role,display_name,created_at) VALUES(?,?,?,?,?,?)', (identifier, identifier+'@example.test', 'not-a-password', 'DOCTOR', 'Rollback test', '2026-01-01'))
            raise RuntimeError('Injected transaction failure')
    with store.connection() as db:
        assert not db.execute('SELECT 1 FROM users WHERE user_id=?', (identifier,)).fetchone()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute('INSERT INTO clinician_assignments VALUES(?,?,?)', ('missing', 'missing', '2026-01-01'))
    assert client.put(f'/records/{ENCOUNTER}/prescription', json=plan()).status_code == 200
    assert client.post(f'/doctor/encounters/{ENCOUNTER}/finalize').status_code == 200
    with store.connection() as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE finalized_records SET snapshot_json='{}' WHERE encounter_id=?", (ENCOUNTER,))
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_registration_login_validation_and_duplicates(client):
    payload = {'name':'Synthetic validation patient', 'email':f'{uuid4().hex}@example.test', 'password':'SyntheticPass!2026', 'age':30, 'gender':'Other', 'language':'en'}
    for changes in [{'age': -1}, {'age': 131}, {'gender':'invalid'}, {'email':'invalid'}, {'name':''}, {'password':'short'}, {'language':'invalid'}]:
        assert client.post('/auth/register', json={**payload, **changes}).status_code == 422
    assert client.post('/auth/register', json={}).status_code == 422
    created = client.post('/auth/register', json=payload)
    assert created.status_code == 201, created.text
    assert client.post('/auth/register', json=payload).status_code == 409
    assert client.get('/auth/me').json()['user']['patient_id'] == created.json()['patient_id']
    assert client.post('/auth/login', json={'email':payload['email'], 'password':'IncorrectPass!2026'}).status_code == 401
    assert client.post('/auth/login', json={}).status_code == 422


def test_ocr_outage_preserves_source_and_retry_processes_it(client, monkeypatch):
    import backend.app.document_processing as processing
    started = _new_encounter(client)
    encounter = started['encounter_id']
    assert client.post('/interviews/consents', json={'patient_id':'P1001', 'consent_type':'DOCUMENT_PROCESSING'}).status_code == 201
    original = processing._extract_pdf_pages
    def unavailable(*args):
        raise RuntimeError('TEXT_EXTRACTION_UNAVAILABLE')
    monkeypatch.setattr(processing, '_extract_pdf_pages', unavailable)
    response = client.post(f'/documents/encounters/{encounter}', files={'file':('ocr-outage.pdf',document_bytes(),'application/pdf')})
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved['processing_status'] == 'NEEDS_REVIEW'
    extracted = client.get(f"/documents/{saved['document_id']}/extraction").json()
    assert extracted['error_code'] == 'TEXT_EXTRACTION_UNAVAILABLE'
    assert not extracted['entities']
    assert client.get(f"/documents/{saved['document_id']}/file").content.startswith(b'%PDF')
    monkeypatch.setattr(processing, '_extract_pdf_pages', original)
    retried = client.post(f"/documents/{saved['document_id']}/retry")
    assert retried.status_code == 200 and retried.json()['processing_status'] == 'PROCESSED', retried.text
