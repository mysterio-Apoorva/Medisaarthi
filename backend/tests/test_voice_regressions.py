"""Voice/state regressions. Test doubles here exercise failures, not application responses."""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.clinical_engine import extract_rule_based, red_flags
from backend.tests.test_current_system import _new_encounter, _expect


def facts(text, question='chief_complaint', state=None):
    return {f['field_name']: f['value'] for f in extract_rule_based(text, question, state or {})}


def test_duration_is_not_severity():
    assert 'severity' not in facts('I have chest pain for 3 days')
    assert 'severity' not in facts('mild', 'severity')
    assert facts('8', 'severity')['severity'] == 8
    assert facts('Pain is 8 out of 10')['severity'] == 8


def test_negation_is_scoped_and_unknown_is_not_positive():
    result = facts('No cough but I am sweating')
    assert result['cough'] is False
    assert result['sweating'] is True
    assert 'breathlessness' not in facts('I do not know', 'breathlessness', {'chief_complaint': 'chest pain'})
    assert 'breathlessness' not in facts('sometimes maybe', 'breathlessness', {'chief_complaint': 'chest pain'})
    assert facts('No nausea')['nausea'] is False
    assert facts('not sure about nausea').get('nausea') is None
    assert facts('Norethisterone', 'medications')['medications'] == ['Norethisterone']


def test_legacy_invalid_severity_does_not_crash_safety():
    assert isinstance(red_flags({'chief_complaint': 'chest pain', 'severity': 'severe', 'sweating': True}), list)


def test_start_idempotency_empty_answer_and_draft_not_persisted(monkeypatch):
    with TestClient(app) as client:
        first = _new_encounter(client)
        identifier = first['encounter_id']
        from backend.app.store import store
        with store.connection() as db:
            consent_id = db.execute('SELECT consent_id FROM consents WHERE encounter_id=?', (identifier,)).fetchone()['consent_id']
        repeated = _expect(client.post('/interviews/start', json={'patient_id':'P1001', 'language':'en', 'consent_id':consent_id}), 201)
        assert repeated['encounter_id'] == identifier
        _expect(client.post(f'/interviews/{identifier}/answers', json={'message':'   ', 'expected_revision':0}), 422)
        # Explicit test double: verifies draft semantics separately from real Whisper browser test.
        async def transcription(*args):
            return 'Synthetic transcript for draft persistence test'
        monkeypatch.setattr('backend.app.routes.interviews.transcribe_upload', transcription)
        draft = _expect(client.post(f'/interviews/{identifier}/transcribe', data={'expected_revision':'0'}, files={'file':('audio.wav',b'fixture','audio/wav')}), 200)
        assert draft['saved_as_answer'] is False
        detail = _expect(client.get(f'/interviews/{identifier}'), 200)
        assert detail['revision'] == 0 and detail['answers'] == [] and detail['clinical_state'] == {}


def test_speech_auth_validation_and_unavailable(monkeypatch):
    with TestClient(app) as client:
        _expect(client.post('/speech/synthesize', json={'text':'Hello', 'language':'en'}), 401)
        first = _new_encounter(client)
        _expect(client.post('/speech/synthesize', json={'text':'   ', 'language':'en'}), 422)
        monkeypatch.setenv('TTS_MODEL_EN', 'backend/data/absent-test-voice.onnx')
        _expect(client.post('/speech/synthesize', json={'text':'Hello', 'language':'en'}), 503)
        _expect(client.post(f"/interviews/{first['encounter_id']}/transcribe", data={'expected_revision':'0'}, files={'file':('invalid.wav',b'RIFF0000NOTWAVE','audio/wav')}), 415)
