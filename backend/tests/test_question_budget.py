"""Budget, document and extraction regressions against actual persisted API state."""
import json
from fastapi.testclient import TestClient
from backend.tests.test_current_system import _new_encounter, _expect
from backend.app.main import app
from backend.app.clinical_engine import extract_rule_based
from backend.app.question_budget import plan_question, budget


def test_no_eleventh_question_even_when_answers_are_unknown_and_after_correction():
    with TestClient(app) as client:
        state = _new_encounter(client)
        identifier = state['encounter_id']
        for n in range(10):
            assert state['next_question'] is not None
            state = _expect(client.post(f'/interviews/{identifier}/answers', json={
                'message': 'I have chest pain' if n == 0 else 'I do not know', 'expected_revision': state['revision']}), 200)
            assert state['question_budget']['answered'] == n + 1
            if n < 4: assert state['status'] == 'ACTIVE'
        assert state['status'] == 'PATIENT_REVIEW' and state['next_question'] is None
        assert state['question_budget']['unresolved_fields']
        _expect(client.post(f'/interviews/{identifier}/answers', json={'message': 'Eleventh answer', 'expected_revision': state['revision']}), 409)
        _expect(client.post(f'/interviews/{identifier}/corrections', json={'field_name': 'severity', 'value': 3, 'expected_revision': state['revision']}), 200)
        detail = _expect(client.get(f'/interviews/{identifier}'), 200)
        assert detail['status'] == 'PATIENT_REVIEW' and detail['next_question'] is None
        assert len(detail['answers']) == 10
        # A pre-upgrade active encounter at the cap resumes into review, not a dead end.
        from backend.app.store import store
        with store.connection() as db:
            db.execute("UPDATE encounters SET status='ACTIVE' WHERE encounter_id=?", (identifier,))
        detail = _expect(client.get(f'/interviews/{identifier}'), 200)
        assert detail['status'] == 'PATIENT_REVIEW' and detail['interview_completed']
        assert detail['next_question'] is None and len(detail['answers']) == 10
        # Missing facts remain explicit, but cannot trap the patient after the budget.
        _expect(client.post(f'/interviews/{identifier}/submit', json={'reviewed': True, 'expected_revision': detail['revision']}), 200)


def test_simple_case_finishes_at_five_and_not_before():
    with TestClient(app) as client:
        state = _new_encounter(client)
        identifier = state['encounter_id']
        messages = ['My knee is sore since yesterday, 3 out of 10.',
                    'No medical conditions. No medicines. No known allergies.',
                    'No operations. No family conditions.', 'I sleep well and do not smoke.', 'Nothing else.']
        for i, message in enumerate(messages):
            state = _expect(client.post(f'/interviews/{identifier}/answers', json={'message': message, 'expected_revision': state['revision']}), 200)
            if i < 4: assert state['status'] == 'ACTIVE'
        assert state['status'] == 'PATIENT_REVIEW', state
        assert state['question_budget']['answered'] == 5
        assert state['question_budget']['reason'] == 'sufficient_information'


def test_grouped_extraction_does_not_copy_whole_answer_to_unstated_fields():
    fields = ['past_medical_history', 'medications', 'allergies']
    facts = extract_rule_based('I take metformin 500 mg. No known allergies.', fields[0], {'_question_fields': fields})
    result = {f['field_name']: f['value'] for f in facts}
    assert 'past_medical_history' not in result
    assert result['medications'] == ['i take metformin 500 mg']
    assert result['allergies'] == []
    assert not budget({'chief_complaint': 'knee soreness'}, [])['complete']


def test_hindi_multi_field_answers_and_spoken_severity():
    facts = extract_rule_based('मेरे घुटने में कल से दर्द है, दर्द तीन है दस में से।', 'chief_complaint', {})
    values = {f['field_name']: f['value'] for f in facts}
    assert values['duration'] == 'since yesterday' and values['severity'] == 3
    facts = extract_rule_based('कोई पुरानी बीमारी नहीं है। कोई दवा नहीं लेता। कोई एलर्जी नहीं है।', 'past_medical_history', {'_question_fields': ['past_medical_history', 'medications', 'allergies']})
    assert {f['field_name']:f['value'] for f in facts} == {'past_medical_history':[], 'medications':[], 'allergies':[]}


def test_red_flag_does_not_wait_for_model_and_conflict_stays_visible(monkeypatch):
    from backend.app.ai.orchestrator import orchestrator
    def unexpected_model(*args): raise AssertionError('Safety must not wait for the LLM')
    monkeypatch.setattr(orchestrator.intake, 'run', unexpected_model)
    result = orchestrator.interpret('I have chest pain and I am short of breath.', 'chief_complaint', {})
    assert result.provider == 'clinical_rules'
    assert any(f.field_name == 'breathlessness' and f.value is True for f in result.extraction.facts)


def test_model_cannot_copy_a_previous_answer_into_a_new_field():
    from backend.app.ai.providers import ExtractedFact, _is_safe_model_fact
    fact = ExtractedFact(field_name='duration', value='10 out of 10', evidence='No medicines', confidence=.9)
    assert not _is_safe_model_fact(fact, 'no medicines', 'duration', ['duration', 'severity'])


def test_adaptive_safety_screen_and_ayush_context():
    chest = plan_question({'chief_complaint': 'chest pain'}, 'en', 'MODERN', [])
    head = plan_question({'chief_complaint': 'headache'}, 'hi', 'MODERN', [])
    assert chest['id'] == 'breathlessness' and 'sweating' in chest['fields']
    assert head['id'] == 'sudden_onset' and head['language'] == 'hi'
    full = {'chief_complaint': 'knee', 'duration': 'two days', 'severity': 2, 'past_medical_history': [], 'medications': [], 'allergies': []}
    ayush = plan_question(full, 'en', 'AYUSH', [])
    assert any(f in ayush['fields'] for f in ('vikriti', 'ahara_vihara'))


def test_report_confirmation_is_grounded_and_persisted_with_provenance():
    from backend.app.store import store, now
    from uuid import uuid4
    with TestClient(app) as client:
        state = _new_encounter(client); identifier = state['encounter_id']
        doc = 'DOC_' + uuid4().hex
        with store.connection() as db:
            actor = db.execute("SELECT user_id FROM users WHERE patient_id='P1001' AND role='PATIENT'").fetchone()['user_id']
            db.execute('INSERT INTO documents(document_id,patient_id,encounter_id,original_name,stored_name,mime_type,size_bytes,processing_status,uploaded_by,uploaded_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (doc, 'P1001', identifier, 'synthetic-prescription.txt', 'synthetic', 'text/plain', 1, 'PROCESSED', actor, now()))
            db.execute('INSERT INTO document_entities(entity_id,document_id,page_number,entity_type,field_name,value_json,evidence,confidence,verification_status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       ('ENT_' + uuid4().hex, doc, 1, 'MEDICATION', 'medications', json.dumps(['Metformin 500 mg twice daily']), 'Metformin 500 mg twice daily', .95, 'NEEDS_VERIFICATION', now(), now()))
        for message in ['My knee hurts since yesterday, 3 out of 10.', 'No medical conditions. No known allergies.']:
            state = _expect(client.post(f'/interviews/{identifier}/answers', json={'message': message, 'expected_revision': state['revision']}), 200)
        assert state['next_question']['id'] == 'medications', state['next_question']
        assert 'Metformin 500 mg twice daily' in state['next_question']['text']
        assert 'medications' not in state['clinical_state']
        state = _expect(client.post(f'/interviews/{identifier}/answers', json={'message': 'Yes, that is correct.', 'expected_revision': state['revision']}), 200)
        assert state['clinical_state']['medications'] == ['Metformin 500 mg twice daily']
        with store.connection() as db:
            fact = db.execute("SELECT * FROM clinical_facts WHERE encounter_id=? AND field_name='medications'", (identifier,)).fetchone()
            assert doc in fact['evidence'] and fact['source'] == 'PATIENT_REPORTED'
            assert db.execute("SELECT 1 FROM timeline_events WHERE encounter_id=? AND event_type='INTERVIEW_MEDICATIONS'", (identifier,)).fetchone()
