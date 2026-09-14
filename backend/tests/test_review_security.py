import io
import json
import pytest
import pymupdf
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.store import store
from backend.tests.test_current_system import _new_encounter, _expect


def clinician(client):
    _expect(client.post('/auth/login',json={'email':'doctor.demo@medikiosk.local','password':'DemoPass!2026'}),200)


def test_review_consent_status_locks_and_fhir():
    with TestClient(app) as client:
        first = _new_encounter(client)
        identifier = first['encounter_id']
        # Direct patient corrections are typed, persisted and revision checked.
        _expect(client.post(f'/interviews/{identifier}/corrections',json={'field_name':'severity','value':'not a number','expected_revision':0}),422)
        for field,value in [('chief_complaint','fatigue'),('duration','3 days'),('severity',5),('breathlessness',False),('onset','gradual'),('fever',False)]:
            revision = client.get(f'/interviews/{identifier}').json()['revision']
            _expect(client.post(f'/interviews/{identifier}/corrections',json={'field_name':field,'value':value,'expected_revision':revision}),200)
        # Corrections do not spend clinical questions or bypass the five-turn minimum.
        for _ in range(5):
            current = client.get(f'/interviews/{identifier}').json()
            _expect(client.post(f'/interviews/{identifier}/answers', json={'message': 'None', 'expected_revision': current['revision']}), 200)
        revision = client.get(f'/interviews/{identifier}').json()['revision']
        _expect(client.post(f'/interviews/{identifier}/submit',json={'expected_revision':revision}),409)
        _expect(client.post(f'/interviews/{identifier}/submit',json={'expected_revision':revision,'reviewed':True}),200)
        _expect(client.post(f'/interviews/{identifier}/submit',json={'reviewed':True}),409)
        _expect(client.post(f'/interviews/{identifier}/corrections',json={'field_name':'severity','value':7,'expected_revision':revision}),409)
        clinician(client)
        bundle = _expect(client.get(f'/doctor/encounters/{identifier}/fhir'),200)
        assert bundle['resourceType']=='Bundle'
        encounter = next(e['resource'] for e in bundle['entry'] if e['resource']['resourceType']=='Encounter')
        assert encounter['status']=='in-progress' and '_' not in encounter['id']
        _expect(client.post(f'/doctor/encounters/{identifier}/finalize'),200)
        _expect(client.post('/doctor/patients/P1001/facts',json={'field_name':'severity','value':2}),409)
        _expect(client.post(f'/doctor/encounters/{identifier}/finalize'),409)
        with store.connection() as db:
            consent = db.execute("SELECT * FROM consents WHERE encounter_id=? AND consent_type='RECORD_SUBMISSION'",(identifier,)).fetchone()
            assert consent and consent['version'] and consent['recorded_by']


def test_document_signature_access_and_real_pdf_extraction():
    with TestClient(app) as client:
        first = _new_encounter(client)
        identifier=first['encounter_id']
        _expect(client.post('/interviews/consents',json={'patient_id':'P1001','consent_type':'DOCUMENT_PROCESSING'}),201)
        _expect(client.post(f'/documents/encounters/{identifier}',files={'file':('bad.pdf',b'<script>alert(1)</script>','application/pdf')}),415)
        pdf=pymupdf.open(); page=pdf.new_page(); page.insert_text((50,50),'SYNTHETIC patient report\nTablet Aspirin 75 mg\nTablet Metformin 500 mg'); content=pdf.tobytes(); pdf.close()
        document=_expect(client.post(f'/documents/encounters/{identifier}',files={'file':('synthetic.pdf',content,'application/pdf')}),201)
        extracted=_expect(client.get(f"/documents/{document['document_id']}/extraction"),200)
        assert 'Aspirin' in extracted['text'] and len(extracted['facts'][0]['value'])==2
        assert client.get(f"/documents/{document['document_id']}/file").content.startswith(b'%PDF-')
        client.post('/auth/logout')
        _expect(client.get(f"/documents/{document['document_id']}/file"),401)


def test_csrf_origin_and_expired_logout():
    with TestClient(app) as client:
        _expect(client.post('/auth/login',headers={'Origin':'https://untrusted.example'},json={'email':'patient.demo@medikiosk.local','password':'DemoPass!2026'}),403)
        _expect(client.post('/auth/logout'),204)


def test_contradictions_are_queued_not_silently_overwritten():
    from backend.app.routes.interviews import _write_fact, _state
    with TestClient(app) as client:
        first=_new_encounter(client)
        with store.connection() as db:
            _write_fact(db,first['encounter_id'],'P1001',{'field_name':'medications','value':['Medicine A'],'evidence':'Synthetic test','confidence':1},'PATIENT_REPORTED')
            accepted=_write_fact(db,first['encounter_id'],'P1001',{'field_name':'medications','value':['Medicine B'],'evidence':'Synthetic contradiction','confidence':1})
            assert accepted is False
            assert _state(db,first['encounter_id'])['medications']==['Medicine A']
            assert db.execute("SELECT COUNT(*) FROM reconciliation_items WHERE encounter_id=? AND status='OPEN'",(first['encounter_id'],)).fetchone()[0]==1
