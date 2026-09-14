"""Browser proof of accessible typing, reports, clinician review and administrator audit.

Run browser_handsfree_e2e.py --scenario suite for real audio conversation tests.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import time
import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from playwright.sync_api import sync_playwright, expect


def main():
    base = os.getenv('E2E_BASE_URL', 'http://127.0.0.1:3000')
    output = Path('backend/data/browser-e2e').resolve()
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True, args=[
            '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
            '--autoplay-policy=no-user-gesture-required',
        ])
        context = browser.new_context(permissions=['microphone'], viewport={'width':1280,'height':1000})
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.set_default_timeout(45000)
        page.goto(f'{base}/patient/identify')
        page.get_by_label('Email', exact=True).fill('patient.demo@medikiosk.local')
        page.get_by_label('Password', exact=True).fill(os.getenv('DEMO_PASSWORD', 'DemoPass!2026'))
        page.get_by_role('button', name='Securely continue').click()
        page.wait_for_url('**/patient/language')
        page.evaluate("localStorage.setItem('medisaarthi_selected_lang','en')")
        page.goto(f'{base}/patient/consent')
        page.get_by_role('checkbox').check()
        page.locator('#agree-continue-button').click()
        page.wait_for_url('**/patient/interview')
        expect(page.locator('#active-question-text')).not_to_be_empty()
        expect(page.get_by_test_id('hands-free-interview')).not_to_have_attribute('data-state', 'IDLE')
        identifier = page.evaluate("localStorage.getItem('medisaarthi_current_interview_id')")
        def snapshot():
            response = context.request.get(f'{base}/api/interviews/{identifier}')
            assert response.ok, response.text()
            return response.json()
        initial = snapshot()
        assert initial['revision'] == 0
        page.reload()
        expect(page.locator('#active-question-text')).not_to_be_empty()
        expect(page.get_by_test_id('hands-free-interview')).not_to_have_attribute('data-state', 'IDLE')
        assert page.evaluate("localStorage.getItem('medisaarthi_current_interview_id')") == identifier
        assert snapshot()['revision'] == 0

        # Voice timing is covered by browser_handsfree_e2e.py. This run verifies the
        # accessible typing path plus the existing document/doctor/admin workflow.
        page.locator('#switch-to-typing-btn').click()
        answers = {
            'chief_complaint':'I have chest pain since yesterday and I am short of breath.',
            'duration':'since yesterday', 'onset':'It started gradually yesterday', 'severity':'8 out of 10',
            'location':'central chest. It feels like heavy pressure. It does not spread anywhere.',
            'character':'heavy pressure. It does not spread anywhere.', 'radiation':'It does not spread anywhere',
            'exertion':'Walking makes it worse and rest makes it better',
            'breathlessness':'I am short of breath. I am sweating. No nausea.', 'sweating':'I am sweating. No nausea.',
            'nausea':'No nausea', 'past_medical_history':'I have hypertension. I take amlodipine 5 mg. No known allergies.',
            'medications':'I take amlodipine 5 mg. No known allergies.', 'allergies':'No known allergies.',
            'past_surgical_history':'None', 'family_history':'None', 'social_history':'None',
            'personal_history':'None', 'review_of_systems':'None',
        }
        for _ in range(10):
            state = snapshot()
            if state['status'] == 'PATIENT_REVIEW': break
            question = state['next_question']['id']
            assert question in answers, question
            page.locator('#patient-answer-input').fill(answers[question])
            with page.expect_response(lambda r: r.url.endswith('/answers'), timeout=90000) as turn:
                page.get_by_role('button', name='Use this answer', exact=True).click()
            assert turn.value.ok, turn.value.text()
        state = snapshot()
        assert state['status'] == 'PATIENT_REVIEW'
        assert 5 <= state['question_budget']['answered'] <= 10
        assert any(flag['code'] == 'CHEST_PAIN_BREATHLESSNESS' for flag in state['priority_flags'])
        draft = state['answers'][0]['answer_text']
        page.locator('#view-completed-button').click()
        page.wait_for_url('**/patient/review')
        expect(page.get_by_role('heading', name='Review your information')).to_be_visible()
        page.get_by_role('textbox', name='severity', exact=True).fill('7')
        with page.expect_response(lambda r: r.url.endswith('/corrections')) as correction:
            page.get_by_role('button', name='Save severity', exact=True).click()
        assert correction.value.ok, correction.value.text()
        assert snapshot()['clinical_state']['severity'] == 7
        report = output / 'synthetic-report.pdf'
        pdf = pymupdf.open()
        report_page = pdf.new_page()
        report_page.insert_text((72,72), 'SYNTHETIC TEST REPORT - NOT A REAL PATIENT\nPatient report\nTablet Aspirin 75 mg\nAllergies: penicillin')
        pdf.save(report)
        pdf.close()
        with page.expect_response(lambda r: '/documents/encounters/' in r.url and r.request.method=='POST', timeout=60000) as upload:
            page.locator('input[type=file]').set_input_files(str(report))
        assert upload.value.status == 201, upload.value.text()
        expect(page.get_by_text('synthetic-report.pdf', exact=False).first).to_be_visible()
        page.get_by_role('button', name='Review extracted text').click()
        expect(page.locator('pre')).to_contain_text('Aspirin')
        page.get_by_role('checkbox').check()
        page.locator('#submit-reviewed-intake').click()
        page.wait_for_url('**/patient/completed')
        assert snapshot()['status'] == 'SUBMITTED'
        print('PASS: reviewed correction, PDF extraction, submission consent', flush=True)

        page.goto(f'{base}/doctor/login')
        page.get_by_label('Hospital email').fill('doctor.demo@medikiosk.local')
        page.get_by_label('Password', exact=True).fill(os.getenv('DEMO_PASSWORD','DemoPass!2026'))
        page.get_by_role('button', name='Sign in securely').click()
        page.wait_for_url(f'{base}/doctor')
        page.goto(f'{base}/doctor/patients/P1001')
        expect(page.locator('#patient-name-header')).to_be_visible()
        page.get_by_text('Clinical fact provenance', exact=True).click()
        expect(page.get_by_text('PATIENT_REPORTED · REPORTED', exact=False).first).to_be_visible()
        page.get_by_role('button', name='Generate grounded AI summary').click()
        expect(page.get_by_test_id('grounded-ai-summary')).to_be_visible(timeout=120000)
        assert page.get_by_test_id('reconciliation-item').count() >= 2
        # Reject a conflicting medication and approve the document allergy, with real API persistence.
        first_item = page.get_by_test_id('reconciliation-item').first
        first_item.get_by_role('button', name='Reject incoming').click()
        expect(page.get_by_test_id('reconciliation-item')).to_have_count(1)
        page.get_by_test_id('reconciliation-item').get_by_role('button', name='Approve incoming').click()
        expect(page.get_by_test_id('reconciliation-item')).to_have_count(0)
        with page.expect_download() as download:
            page.get_by_role('link', name='Download local FHIR R4 bundle').click()
        downloaded = Path(download.value.path()).read_text(encoding='utf-8')
        assert json.loads(downloaded)['resourceType'] == 'Bundle'
        page.locator('#verify-summary-btn').click()
        with page.expect_response(lambda r: r.url.endswith('/finalize')) as finalized:
            page.locator('#confirm-verify-btn').click()
        assert finalized.value.ok, finalized.value.text()
        assert snapshot()['status'] == 'FINALIZED'
        page.reload()
        expect(page.get_by_role('button', name='Finalized', exact=True)).to_be_disabled()
        page.screenshot(path=str(output / 'doctor-finalized.png'), full_page=True)
        print('PASS: doctor source review, real model summary, reconciliation, FHIR, finalization', flush=True)
        page.goto(f'{base}/doctor/login')
        page.get_by_label('Hospital email').fill('admin.demo@medikiosk.local')
        page.get_by_label('Password', exact=True).fill(os.getenv('DEMO_PASSWORD','DemoPass!2026'))
        page.get_by_role('button', name='Sign in securely').click()
        page.wait_for_url(f'{base}/admin')
        expect(page.get_by_text('ENCOUNTER_FINALIZED', exact=True).first).to_be_visible()
        print('PASS: admin login and finalization audit visible', flush=True)
        assert not errors, errors
        print(json.dumps({'result':'PASS', 'encounter_id':identifier, 'typed_answer':draft, 'tests':['cookie login','consent','idempotent refresh','bounded typed interview','corrected answer persisted','safety alert','document extraction','doctor reconciliation','FHIR','finalization','admin audit','no browser runtime errors']}, indent=2))
        browser.close()


if __name__ == '__main__':
    main()
