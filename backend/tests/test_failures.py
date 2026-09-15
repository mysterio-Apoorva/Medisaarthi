import json
import sqlite3
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.store import store
from backend.app.ai.providers import AIProvider, ProviderManager, OllamaProvider
from backend.app.clinical_engine import next_question, detect_complaint, runtime_ontology
from backend.tests.test_current_system import _new_encounter, _expect


def test_failed_model_never_substitutes_rules(monkeypatch):
    monkeypatch.setenv('AI_PROVIDER','ollama')
    monkeypatch.setenv('AI_FALLBACK_MODELS','')
    def unavailable(*args): raise RuntimeError('Deliberate outage test')
    monkeypatch.setattr(OllamaProvider,'extract',unavailable)
    manager=ProviderManager()
    with pytest.raises(RuntimeError, match='unavailable'):
        manager.extract('I have chest pain since yesterday','chief_complaint',{})
    assert manager.snapshot()[0]['cooldown_seconds']>0


def test_external_ai_is_opt_in(monkeypatch):
    monkeypatch.setenv('ALLOW_EXTERNAL_AI','false')
    with pytest.raises(RuntimeError,match='explicit configuration'):
        OllamaProvider(base_url='https://external.example').generate('Synthetic test')


def test_expired_session_denied():
    with TestClient(app) as client:
        _new_encounter(client)
        with store.connection() as db:
            db.execute("UPDATE sessions SET expires_at='2000-01-01T00:00:00+00:00'")
        _expect(client.get('/patients/P1001'),401)
        _expect(client.post('/auth/logout'),204)


def test_database_failure_health_is_safe(monkeypatch):
    with TestClient(app) as client:
        def unavailable(): raise sqlite3.OperationalError('Test-only unavailable database')
        monkeypatch.setattr(store,'connection',unavailable)
        response=client.get('/health')
        assert response.status_code==503
        assert 'Test-only' not in response.text


def test_whisper_outage_does_not_record_answer(monkeypatch):
    from backend.app.voice import SpeechToTextUnavailable
    with TestClient(app) as client:
        first=_new_encounter(client)
        async def unavailable(*args): raise SpeechToTextUnavailable('Deliberate test')
        monkeypatch.setattr('backend.app.routes.interviews.transcribe_upload',unavailable)
        _expect(client.post(f"/interviews/{first['encounter_id']}/transcribe",data={'expected_revision':'0'},files={'file':('voice.wav',b'fixture','audio/wav')}),503)
        result=client.get(f"/interviews/{first['encounter_id']}").json()
        assert result['answers']==[] and result['revision']==0


def test_admin_ontology_affects_questions_and_is_validated():
    with TestClient(app) as client:
        _expect(client.post('/auth/login',json={'email':'admin.demo@medikiosk.local','password':'DemoPass!2026'}),200)
        _expect(client.put('/admin/ontology/TEST_TERM',json={'concept':'synthetic throat symptom','payload':{'synonyms':['synthetic sore throat'],'required':['duration','fever']},'enabled':True}),200)
        assert detect_complaint('synthetic sore throat')=='synthetic throat symptom'
        assert next_question({'chief_complaint':'synthetic throat symptom','duration':'today'},'en')['id']=='fever'
        _expect(client.put('/admin/ontology/TEST_BAD',json={'concept':'bad field','payload':{'required':['unsupported_field']},'enabled':True}),422)
        _expect(client.put('/admin/ontology/TEST_TERM',json={'concept':'synthetic throat symptom','payload':{'synonyms':['synthetic sore throat'],'required':['duration','fever']},'enabled':False}),200)


def test_oversized_document_is_rejected():
    with TestClient(app) as client:
        first=_new_encounter(client)
        _expect(client.post('/interviews/consents',json={'patient_id':'P1001','consent_type':'DOCUMENT_PROCESSING'}),201)
        _expect(client.post(f"/documents/encounters/{first['encounter_id']}",files={'file':('large.pdf',b'%PDF-'+b'0'*(10*1024*1024),'application/pdf')}),413)


def test_rag_outage_does_not_break_core_health(monkeypatch):
    with TestClient(app) as client:
        _expect(client.post('/auth/login',json={'email':'doctor.demo@medikiosk.local','password':'DemoPass!2026'}),200)
        def unavailable(*args): raise RuntimeError('Test embedding outage')
        monkeypatch.setattr(OllamaProvider,'embed',unavailable)
        _expect(client.post('/knowledge/search',json={'query':'synthetic reference'}),503)
        _expect(client.get('/health'),200)
