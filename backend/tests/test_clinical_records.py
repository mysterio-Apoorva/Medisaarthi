"""Synthetic inputs test real SQLite, authorization, finalization and PDF rendering."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import unicodedata
from uuid import uuid4

import pymupdf
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.store import store


def login(client, role):
    response = client.post('/auth/login', json={'email': f'{role}.demo@medikiosk.local', 'password': 'DemoPass!2026'})
    assert response.status_code == 200, response.text


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'path', tmp_path / 'records.sqlite3')
    with TestClient(app) as client:
        login(client, 'doctor')
        yield client


ENCOUNTER = 'ENC_SYNTHETIC_CHEST_1001'


def plan(**changes):
    return {'expected_revision': 0, 'medicines': [{'name': 'Synthetic medicine', 'strength': '10 test units', 'dose': 'one test unit', 'frequency': 'once daily', 'duration': 'three days', 'route': 'oral', 'instructions': 'Synthetic per-medicine instructions'}], 'allergies_reviewed': True, 'allergy_review': [], 'advice': 'Synthetic clinician instructions for integration testing.', **changes}


def measurement(**changes):
    return {'kind': 'VITAL', 'name': 'Synthetic reading', 'value': 97, 'unit': '%', 'measured_at': datetime.now(timezone.utc).isoformat(), 'request_id': str(uuid4()), **changes}


def test_observation_prescription_pdf_followup_persistence(client):
    base = f'/records/{ENCOUNTER}'
    m = measurement()
    added = client.post(base + '/observations', json=m)
    assert added.status_code == 201, added.text
    assert client.post(base + '/observations', json=m).json()['observation_id'] == added.json()['observation_id']
    assert client.post(base + '/observations', json={**m, 'value': 96}).status_code == 409
    saved = client.put(base + '/prescription', json=plan())
    assert saved.status_code == 200, saved.text
    assert client.put(base + '/prescription', json=plan()).status_code == 409
    # New request/connection retrieves what the database saved.
    retrieved = client.get(base).json()
    assert retrieved['observations'][0]['value'] == m['value']
    assert retrieved['prescription']['medicines'] == plan()['medicines']
    result = client.post(f'/doctor/encounters/{ENCOUNTER}/finalize')
    assert result.status_code == 200, result.text
    assert client.put(base + '/prescription', json=plan(expected_revision=1)).status_code == 409
    assert client.post(base + '/observations', json=measurement()).status_code == 409
    pdf = client.get(base + '/pdf')
    assert pdf.status_code == 200, pdf.text
    with pymupdf.open(stream=pdf.content, filetype='pdf') as document:
        text = ''.join(page.get_text() for page in document)
        assert all(abs(page.rect.width - 595) < 1 and abs(page.rect.height - 842) < 1 for page in document)
        for value in ['Synthetic medicine', 'one test unit', 'once daily', 'three days', 'oral', '97', 'Synthetic clinician instructions']:
            assert value in text
    with store.connection() as db:
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        snapshot = json.loads(db.execute('SELECT snapshot_json FROM finalized_records').fetchone()[0])
        assert snapshot['prescription']['medicines'] == plan()['medicines']
    login(client, 'patient')
    assert client.get(base + '/pdf').status_code == 200
    session = client.post(f"/follow-ups/plans/{result.json()['follow_up_plan_id']}/sessions")
    assert session.status_code == 201, session.text
    context = session.json()['record_context']
    assert 'Synthetic medicine' in context['medications'][0]
    assert 'amlodipine' not in str(context['medications'])
    answer = client.post(f"/follow-ups/sessions/{session.json()['session']['follow_up_session_id']}/answers", json={'question_id': session.json()['next_question']['id'], 'message': 'My symptoms are getting worse', 'expected_revision': 0})
    assert answer.status_code == 200, answer.text
    assert answer.json()['alerts']
    with store.connection() as db:
        assert db.execute("SELECT 1 FROM timeline_events WHERE event_type='FOLLOW_UP_RESPONSE'").fetchone()


@pytest.mark.parametrize('changes', [{'value': -2}, {'value': 101}, {'name': ' '}, {'unit': ''}, {'kind': 'DEVICE'}, {'measured_at': 'invalid'}, {'measured_at': '2039-01-01T00:00:00Z'}, {'request_id': 'invalid'}])
def test_invalid_observations_do_not_persist(client, changes):
    assert client.post(f'/records/{ENCOUNTER}/observations', json=measurement(**changes)).status_code == 422
    assert client.get(f'/records/{ENCOUNTER}').json()['observations'] == []


def test_record_permissions_and_absent_resources(client):
    base = f'/records/{ENCOUNTER}'
    client.post('/auth/logout')
    assert client.get(base).status_code == 401
    assert client.put(base + '/prescription', json=plan()).status_code == 401
    login(client, 'patient')
    assert client.put(base + '/prescription', json=plan()).status_code == 403
    assert client.post(f'/doctor/encounters/{ENCOUNTER}/finalize').status_code == 403
    assert client.post(base + '/observations', json=measurement()).status_code == 409
    assert client.get('/records/missing').status_code == 404
    assert client.get(base + '/pdf').status_code == 409
    # Fresh registration has no access to another patient's resources.
    registered = client.post('/auth/register', json={'name': 'Synthetic Other', 'age': 30, 'gender': 'Other', 'language': 'en', 'email': f'{uuid4().hex}@example.test', 'password': 'SyntheticPassword!29'})
    assert registered.status_code == 201, registered.text
    assert client.get(base).status_code == 403
    assert client.get(base + '/pdf').status_code == 403


def test_prescription_validation_and_concurrent_writes(client):
    base = f'/records/{ENCOUNTER}/prescription'
    for invalid in [plan(medicines=[]), plan(advice=' '), plan(medicines=[{'name': 'incomplete'}]), plan(medicines=plan()['medicines'] * 2)]:
        assert client.put(base, json=invalid).status_code == 422
    cookies = dict(client.cookies)
    def save(_):
        with TestClient(app) as concurrent:
            concurrent.cookies.update(cookies)
            return concurrent.put(base, json=plan()).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(save, range(2))) == [200, 409]


def test_void_and_pdf_failure_are_explicit(client, monkeypatch):
    base = f'/records/{ENCOUNTER}'
    oid = client.post(base + '/observations', json=measurement()).json()['observation_id']
    assert client.post(base + f'/observations/{oid}/void', json={'reason': 'Entry error'}).status_code == 200
    assert client.post(base + f'/observations/{oid}/void', json={'reason': 'Entry error'}).status_code == 409
    assert client.put(base + '/prescription', json=plan(medicines=[], no_medicines_reason='No medicine indicated in synthetic scenario')).status_code == 200
    assert client.post(f'/doctor/encounters/{ENCOUNTER}/finalize').status_code == 200
    def fail(_):
        raise RuntimeError('Synthetic PDF failure')
    monkeypatch.setattr('backend.app.pdf_service.render_record', fail)
    failed = client.get(base + '/pdf')
    assert failed.status_code == 503
    assert 'retry' in failed.json()['detail']


def test_bmi_sources_withdrawal_duplicate_and_timeline(client):
    base = f'/records/{ENCOUNTER}'
    weight = measurement(name='Weight', value=72, unit='kg')
    saved_weight = client.post(base + '/observations', json=weight).json()
    assert not any(r['name'] == 'BMI' for r in client.get(base).json()['observations'])
    duplicate = {**weight, 'name': 'weight', 'request_id': str(uuid4())}
    assert client.post(base + '/observations', json=duplicate).status_code == 409
    height = client.post(base + '/observations', json=measurement(name='Height', value=180, unit='cm')).json()
    bmi = next(r for r in client.get(base).json()['observations'] if r['name'] == 'BMI')
    assert bmi['value'] == 22.22 and bmi['source'] == 'CALCULATED'
    assert json.loads(bmi['metadata_json'])['input_observation_ids'] == [saved_weight['observation_id'], height['observation_id']]
    assert client.post(base + f"/observations/{bmi['observation_id']}/void", json={'reason': 'Direct derived edit'}).status_code == 409
    assert client.post(base + f"/observations/{height['observation_id']}/void", json={'reason': 'Incorrect source height'}).status_code == 200
    assert not any(r['name'] == 'BMI' and not r['voided_at'] for r in client.get(base).json()['observations'])
    client.post(base + '/observations', json=measurement(name='Height', value=1.8, unit='m'))
    active = [r for r in client.get(base).json()['observations'] if r['name'] == 'BMI' and not r['voided_at']]
    assert len(active) == 1 and active[0]['value'] == 22.22
    timeline = client.get('/doctor/patients/P1001/timeline').json()
    assert any('BMI' in (r['detail'] or '') and r['event_type'] == 'OBSERVATION_WITHDRAWN' for r in timeline)
    assert client.put(base + '/prescription', json=plan()).status_code == 200
    assert client.post(f'/doctor/encounters/{ENCOUNTER}/finalize').status_code == 200
    with pymupdf.open(stream=client.get(base + '/pdf').content, filetype='pdf') as pdf:
        text = ''.join(p.get_text() for p in pdf)
        assert '22.22' in text and 'height_m' in text and saved_weight['observation_id'] in text


@pytest.mark.parametrize('name,unit,value', [('Height', 'kg', 170), ('Weight', 'cm', 70), ('Pulse', 'kg', 70), ('SpO2', 'bpm', 97), ('Temperature', 'kg', 37), ('Systolic blood pressure', '%', 90)])
def test_named_vital_units_are_validated(client, name, unit, value):
    assert client.post(f'/records/{ENCOUNTER}/observations', json=measurement(name=name, unit=unit, value=value)).status_code == 422
    assert client.get(f'/records/{ENCOUNTER}').json()['observations'] == []


def test_allergy_acknowledgement_stale_review_and_finalization(client):
    base = f'/records/{ENCOUNTER}'
    assert client.put(base + '/prescription', json=plan(allergies_reviewed=False)).status_code == 422
    assert client.put(base + '/prescription', json=plan()).status_code == 200
    corrected = client.post('/doctor/patients/P1001/facts', json={'field_name': 'allergies', 'value': ['Synthetic recorded allergy'], 'reason': 'New patient report'})
    assert corrected.status_code == 200
    assert client.get(base).json()['allergies'] == ['Synthetic recorded allergy']
    assert client.post(f'/doctor/encounters/{ENCOUNTER}/finalize').status_code == 409
    assert client.put(base + '/prescription', json=plan(expected_revision=1)).status_code == 409
    saved = client.put(base + '/prescription', json=plan(expected_revision=1, allergy_review=['Synthetic recorded allergy']))
    assert saved.status_code == 200, saved.text
    review = saved.json()['allergy_review']
    assert review['allergies'] == ['Synthetic recorded allergy'] and review['reviewed_by']
    assert client.post(f'/doctor/encounters/{ENCOUNTER}/finalize').status_code == 200


@pytest.mark.parametrize('field', ['strength', 'instructions'])
def test_medicine_requires_separate_strength_and_instructions(client, field):
    payload = plan()
    del payload['medicines'][0][field]
    assert client.put(f'/records/{ENCOUNTER}/prescription', json=payload).status_code == 422
    assert client.get(f'/records/{ENCOUNTER}').json()['prescription'] is None


def test_finalization_never_ignores_an_unsaved_treatment_plan(client):
    assert client.put(f'/records/{ENCOUNTER}/prescription', json=plan()).status_code == 200
    response = client.post(f'/doctor/encounters/{ENCOUNTER}/finalize', json={'treatment_plan': 'Unsaved changed advice'})
    assert response.status_code == 422
    assert client.get(f'/records/{ENCOUNTER}').json()['status'] == 'SUBMITTED'


def test_multipage_pdf_contains_all_stored_medicine_instructions(client):
    medicines = [{**plan()['medicines'][0], 'name': f'Synthetic medicine {index}', 'instructions': f'Instruction marker {index}. ' + 'Synthetic instruction text. ' * 12} for index in range(30)]
    base = f'/records/{ENCOUNTER}'
    assert client.put(base + '/prescription', json=plan(medicines=medicines)).status_code == 200
    assert client.post(f'/doctor/encounters/{ENCOUNTER}/finalize').status_code == 200
    with pymupdf.open(stream=client.get(base + '/pdf').content, filetype='pdf') as pdf:
        assert len(pdf) > 1
        text = ' '.join(unicodedata.normalize('NFKC', ' '.join(p.get_text() for p in pdf)).split())
        assert all(abs(p.rect.width - 595) < 1 and abs(p.rect.height - 842) < 1 for p in pdf)
        for index in range(30):
            assert f'Instruction marker {index}.' in text
        assert 'Doctor advice and follow-up' in text and 'Synthetic clinician instructions' in text
