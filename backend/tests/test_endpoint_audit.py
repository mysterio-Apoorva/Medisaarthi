"""Every registered endpoint gets an explicit authentication and outage check."""
import re
import sqlite3

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from backend.app.main import app, _request_windows
from backend.app.store import store
from backend.tests.test_current_system import _new_encounter

PUBLIC = {('GET', '/'), ('GET', '/health'), ('POST', '/auth/login'), ('POST', '/auth/register'), ('POST', '/auth/logout')}
ROUTES = [(method.upper(), path) for path, operations in app.openapi()['paths'].items() for method in operations if method.upper() in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE'}]
PROTECTED = [route for route in ROUTES if route not in PUBLIC]


@pytest.mark.parametrize('method,path', PROTECTED)
def test_every_protected_endpoint_requires_authentication(method, path):
    _request_windows.clear()
    with TestClient(app) as client:
        response = client.request(method, re.sub(r'\{[^}]+\}', 'missing', path), json={})
        assert response.status_code == 401, (method, path, response.text)


@pytest.mark.parametrize('method,path', PROTECTED)
def test_database_outage_is_explicit_for_every_protected_endpoint(method, path, monkeypatch):
    with TestClient(app) as client:
        def unavailable():
            raise sqlite3.OperationalError('Injected database outage')
        monkeypatch.setattr(store, 'connection', unavailable)
        response = client.request(method, re.sub(r'\{[^}]+\}', 'missing', path), headers={'Authorization': 'Bearer synthetic-token'}, json={})
        assert response.status_code == 503, (method, path, response.text)
        assert 'database' in response.json()['detail']


def test_patient_cannot_invoke_staff_endpoints():
    _request_windows.clear()
    with TestClient(app) as client:
        assert client.post('/auth/login', json={'email': 'patient.demo@medikiosk.local', 'password': 'DemoPass!2026'}).status_code == 200
        staff = [route for route in PROTECTED if route[1].startswith(('/doctor/', '/admin/', '/knowledge/')) or route[1].endswith(('/prescription', '/acknowledge'))]
        for method, path in staff:
            response = client.request(method, re.sub(r'\{[^}]+\}', 'missing', path), json={})
            assert response.status_code == 403, (method, path, response.text)


def test_question_generation_failure_preserves_saved_answer(monkeypatch):
    with TestClient(app) as client:
        initial = _new_encounter(client)
        identifier = initial['encounter_id']
        def unavailable(*args, **kwargs):
            raise HTTPException(503, 'Injected AI question outage')
        monkeypatch.setattr('backend.app.routes.interviews.phrase_question', unavailable)
        response = client.post(f'/interviews/{identifier}/answers', json={'message': 'I have fatigue since yesterday', 'expected_revision': initial['revision']})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body['revision'] == initial['revision'] + 1
        assert body['next_question']['text'] == ''
        assert body['ai_warning']
        retrieved = client.get(f'/interviews/{identifier}').json()
        assert len(retrieved['answers']) == 1
        assert client.post(f'/interviews/{identifier}/answers', json={'message': 'duplicate', 'expected_revision': initial['revision']}).status_code == 409


def test_manual_mode_is_explicit_and_authorized():
    with TestClient(app) as client:
        initial = _new_encounter(client)
        identifier = initial['encounter_id']
        changed = client.patch(f'/interviews/{identifier}/mode', json={'processing_mode': 'MANUAL'})
        assert changed.status_code == 200
        snapshot = client.get(f'/interviews/{identifier}').json()
        assert snapshot['encounter']['processing_mode'] == 'MANUAL'
        assert snapshot['next_question']['generation_method'] == 'MANUAL_PROTOCOL'
        assert client.patch(f'/interviews/{identifier}/mode', json={'processing_mode': 'invalid'}).status_code == 422
